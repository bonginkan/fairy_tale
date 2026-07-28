#!/usr/bin/env python3
"""Machine gate for the Implementation contract closure record.

The record card is a process obligation; this validator is what makes it
load-bearing. Everything that decides closure is DERIVED from the tables, not
read from a self-declared field:

- the concurrency matrix is checked against the CROSS PRODUCT of the operation
  inventory (self-pairs included), so a hand-listed subset fails instead of
  silently omitting the pair that later becomes a review round;
- read/write intersections are hazard CANDIDATES, not verdicts: the hazard
  kind decides which dispositions are admissible, so commutative,
  snapshot-read and key-partitioned overlaps stay legal instead of being
  over-blocked into needless serialization;
- a safe disposition still has to carry its own proof obligation (commutativity
  and idempotence tests, a snapshot staleness contract, or differing partition
  predicates), so safety cannot be asserted past the evidence;
- fix re-closure is derived from a versioned DIFF against the previous record
  (identities, operations, read/write sets, failure and UNKNOWN behaviour,
  dispositions, serialization points, platform invariants), so the change
  surface itself cannot be under-declared and stale evidence is rejected;
- the operation inventory is compared BOTH ways against a canonical route /
  handler inventory, so omission is caught as well as invention.

Known limit, stated rather than hidden: `disjoint_keyspace` is checked
structurally (both sides partition the same identity with different declared
predicates plus evidence). Proving predicate disjointness semantically is out
of scope for this gate and remains a reviewer judgement.

Usage:
  python3 scripts/implementation_contract_closure.py validate --record r.json \
      [--base previous-record.json]
  python3 scripts/implementation_contract_closure.py sample
  python3 scripts/implementation_contract_closure.py --selftest
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import re
import sys
from datetime import datetime, timezone
import tempfile
from pathlib import Path
from typing import Any, Iterable

SCHEMA_ID = "fairy.implementation-contract-closure.v1"

SAFE_DISPOSITIONS = {"commutative", "read_only_snapshot", "disjoint_keyspace"}
PAIR_DISPOSITIONS = SAFE_DISPOSITIONS | {"serialized", "impossible"}
# Impossibility must be a property of the system. Timing, UI flow and "we never
# saw it" are not properties; `disjoint_keyspace` is a SAFE OVERLAP, not an
# impossibility, and is deliberately absent here.
IMPOSSIBILITY_KINDS = {
    "single_writer_invariant",
    "lock",
    "state_machine_exclusion",
    "lifecycle_exclusion",
}


class Finding(str):
    """A single fail-closed reason."""


def text(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def text_list(value: Any, *, minimum: int = 1) -> bool:
    return (
        isinstance(value, list)
        and len(value) >= minimum
        and all(text(item) for item in value)
    )


def parse_time(value: Any) -> datetime | None:
    """Parse a TIMEZONE-QUALIFIED ISO-8601 timestamp, normalised to UTC.

    A naive timestamp is not accepted: "17:00" is not a fact until the offset
    is known, and silently assuming UTC would make lineage and staleness
    comparisons decide on an invented value. Callers report the rejection as a
    finding — comparisons themselves are always aware-vs-aware, so no
    naive/aware TypeError can occur.
    """
    if not text(value):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def hazards(op_a: dict[str, Any], op_b: dict[str, Any]) -> tuple[set[str], set[str]]:
    """Hazard CANDIDATES between two operations, split by kind.

    An intersection is a candidate, not a verdict: write/write may still be
    commutative or key-partitioned, and read/write may still be a legal
    snapshot read. Only the kind of hazard decides which dispositions are
    admissible — never "they touch the same thing, therefore serialize".
    """
    reads_a, writes_a = set(op_a.get("reads", [])), set(op_a.get("writes", []))
    reads_b, writes_b = set(op_b.get("reads", [])), set(op_b.get("writes", []))
    write_write = writes_a & writes_b
    read_write = ((writes_a & reads_b) | (writes_b & reads_a)) - write_write
    return write_write, read_write


TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "number": (int, float),
    "integer": int,
}


def check_schema_node(node: Any, value: Any, where: str, schema: dict[str, Any]) -> list[str]:
    """Evaluate the subset of JSON Schema this record's schema uses.

    Deliberately dependency-free: the canonical CLI must run in a clean
    checkout. `jsonschema` remains the CI cross-check against this evaluator,
    so the two cannot silently diverge — but the gate does not need it to be
    installed in order to fail closed.
    """
    errors: list[str] = []
    if "$ref" in node:
        ref = node["$ref"]
        if ref.startswith("#/"):
            target: Any = schema
            for part in ref[2:].split("/"):
                target = target.get(part, {}) if isinstance(target, dict) else {}
            return check_schema_node(target, value, where, schema)
        return errors
    if "const" in node and value != node["const"]:
        errors.append(f"{where}: must be {node['const']!r}")
    if "enum" in node and value not in node["enum"]:
        errors.append(f"{where}: must be one of {node['enum']}")
    expected = node.get("type")
    if expected:
        python_type = TYPE_MAP.get(expected)
        if expected == "integer" and isinstance(value, bool):
            errors.append(f"{where}: must be an integer")
            return errors
        if python_type and not isinstance(value, python_type):
            errors.append(f"{where}: must be a JSON {expected}")
            return errors
    if isinstance(value, str):
        if "minLength" in node and len(value) < node["minLength"]:
            errors.append(f"{where}: must not be empty")
        pattern = node.get("pattern")
        if pattern:
            import re

            if not re.match(pattern, value):
                errors.append(f"{where}: does not match {pattern}")
    if isinstance(value, list):
        if "minItems" in node and len(value) < node["minItems"]:
            errors.append(f"{where}: needs at least {node['minItems']} item(s)")
        if "maxItems" in node and len(value) > node["maxItems"]:
            errors.append(f"{where}: allows at most {node['maxItems']} item(s)")
        item_schema = node.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(check_schema_node(item_schema, item, f"{where}[{index}]", schema))
    if isinstance(value, dict):
        properties = node.get("properties", {})
        for field in node.get("required", []):
            if field not in value:
                errors.append(f"{where}.{field}: required")
        if node.get("additionalProperties") is False:
            for field in value:
                if field not in properties:
                    errors.append(f"{where}.{field}: unexpected field")
        for field, sub in properties.items():
            if field in value:
                errors.extend(check_schema_node(sub, value[field], f"{where}.{field}", schema))
    return errors


PROJECT_SURFACE_CONFIG = ".fairy/contract-surface.json"
PROJECT_LINEAGE_LEDGER = ".fairy/contract-closure-lineage.json"
OPERATION_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")


def git_blob(root: Path, rev: str, relative: str) -> tuple[bytes | None, str | None]:
    """Read an authority file from an IMMUTABLE Git object.

    The trusted copy comes from a committed object resolved by git itself, so
    a caller cannot self-trust the working tree (`--trusted-base .` is not a
    revision) and cannot hand over a directory it just wrote.
    """
    import subprocess

    try:
        return (
            subprocess.run(
                ["git", "-C", str(root), "show", f"{rev}:{relative}"],
                capture_output=True,
                check=True,
            ).stdout,
            None,
        )
    except FileNotFoundError:
        return None, "git is not available, so the trusted authority cannot be resolved"
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode("utf-8", "replace").strip().splitlines()
        return None, f"cannot read {relative} at {rev}: {detail[-1] if detail else 'unknown error'}"


def resolve_trusted_base(root: Path, rev: str) -> tuple[str | None, list[str]]:
    """Resolve the trusted revision and prove it is independent of HEAD."""
    import subprocess

    def git(*args: str) -> tuple[int, str]:
        try:
            done = subprocess.run(
                ["git", "-C", str(root), *args], capture_output=True, text=True
            )
        except FileNotFoundError:
            return 127, "git is not available"
        return done.returncode, (done.stdout or done.stderr).strip()

    code, resolved = git("rev-parse", "--verify", f"{rev}^{{commit}}")
    if code != 0:
        return None, [f"trusted base {rev!r} is not a commit ({resolved})"]
    code, head = git("rev-parse", "--verify", "HEAD^{commit}")
    if code != 0:
        return None, [f"cannot resolve HEAD ({head})"]
    if resolved == head:
        return None, [
            f"trusted base {rev!r} resolves to HEAD — a revision cannot vouch for itself"
        ]
    code, _ = git("merge-base", "--is-ancestor", resolved, head)
    if code != 0:
        return None, [
            f"trusted base {rev!r} is not an ancestor of HEAD, so it is not this work's base"
        ]
    return resolved, []


def authority_file(root: Path, relative: str) -> tuple[Path | None, list[str]]:
    """Resolve an authority file, refusing anything but the exact in-tree path.

    Every component must exist with EXACTLY the declared name (so `.FAIRY` on a
    case-insensitive host is not accepted as `.fairy`), nothing on the path may
    be a symlink, and the result must stay inside the repository. An authority
    boundary that can be aliased or redirected is not a boundary.
    """
    errors: list[str] = []
    current = root
    for part in Path(relative).parts:
        if part in {"", ".", ".."} or Path(part).is_absolute():
            return None, [f"{relative}: authority path component {part!r} is not allowed"]
        try:
            names = {entry.name for entry in os.scandir(current)}
        except OSError as error:
            return None, [f"{relative}: cannot read {current.name!r} ({error})"]
        if part not in names:
            return None, [f"{relative}: authority path is missing (no exact entry {part!r})"]
        current = current / part
        if current.is_symlink():
            return None, [f"{relative}: authority path component {part!r} is a symlink — refused"]
    try:
        resolved = current.resolve()
        resolved.relative_to(root.resolve())
    except (OSError, ValueError):
        return None, [f"{relative}: authority file resolves outside the repository"]
    if not resolved.is_file():
        return None, [f"{relative}: authority path is not a regular file"]
    return resolved, errors


def load_authority(root: Path, relative: str, required: dict[str, type]) -> tuple[dict[str, Any] | None, list[str]]:
    """Read an authority JSON fail-closed: a non-object or a wrong-typed field
    disables nothing — it is a finding."""
    path, errors = authority_file(root, relative)
    if path is None:
        return None, errors
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return None, [f"{relative}: not readable UTF-8 JSON ({error})"]
    if not isinstance(value, dict):
        return None, [f"{relative}: must be a JSON object (a list or scalar silently disables enforcement)"]
    for field, expected in required.items():
        if field not in value:
            return None, [f"{relative}: missing required field {field!r}"]
        if not isinstance(value[field], expected):
            return None, [f"{relative}: field {field!r} has the wrong type"]
    value["__bytes__"] = raw
    return value, errors


def discover_operations(root: Path, globs: Iterable[str], pattern: str) -> tuple[set[str], list[str]]:
    """Walk the project surface, refusing to leave the repository.

    Absolute globs, parent-directory escapes and symlinks that resolve outside
    the tree are refused rather than followed: a discovery walk must never read
    a file the repository does not contain, and nothing read is ever echoed
    back — only ids that match the operation-id shape are accepted.
    """
    errors: list[str] = []
    try:
        compiled = re.compile(pattern, re.MULTILINE)
    except re.error as error:
        return set(), [f"{PROJECT_SURFACE_CONFIG}: pattern is not a valid regular expression ({error})"]
    if "operation" not in (compiled.groupindex or {}):
        return set(), [
            f"{PROJECT_SURFACE_CONFIG}: pattern must capture a named group 'operation'"
        ]
    resolved_root = root.resolve()
    found: set[str] = set()
    for glob in globs:
        text_glob = str(glob)
        if Path(text_glob).is_absolute() or ".." in Path(text_glob).parts:
            errors.append(
                f"{PROJECT_SURFACE_CONFIG}: glob {text_glob!r} leaves the repository — discovery is "
                "confined to the tree"
            )
            continue
        try:
            candidates = sorted(root.glob(text_glob))
        except (NotImplementedError, ValueError, OSError) as error:
            errors.append(f"{PROJECT_SURFACE_CONFIG}: glob {text_glob!r} is not usable ({error})")
            continue
        for path in candidates:
            try:
                real = path.resolve()
                real.relative_to(resolved_root)
            except (OSError, ValueError):
                errors.append(
                    f"{PROJECT_SURFACE_CONFIG}: {path.name!r} resolves outside the repository "
                    "(symlink escape refused)"
                )
                continue
            if not real.is_file():
                continue
            try:
                body = real.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                errors.append(f"{PROJECT_SURFACE_CONFIG}: {path.name!r} is not readable UTF-8")
                continue
            for match in compiled.finditer(body):
                candidate = match.group("operation") or ""
                # Never reflect file content: only a well-formed id is taken.
                if OPERATION_ID.match(candidate):
                    found.add(candidate)
                else:
                    errors.append(
                        f"{PROJECT_SURFACE_CONFIG}: {path.name!r} yielded a capture that is not a "
                        "well-formed operation id"
                    )
    return found, errors


def validate_shape(record: Any, schema_path: Path) -> list[Finding]:
    """Strict shape check against the shipped schema, with no external
    dependency: a record the schema rejects never reaches the semantic pass."""
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [Finding(f"schema: cannot load {schema_path}: {error}")]
    return [Finding(f"shape: {message}") for message in check_schema_node(schema, record, "<root>", schema)]


def validate_record(
    record: Any,
    base: Any = None,
    inventory: Iterable[str] | None = None,
    inventory_path: str | None = None,
    base_path: str | None = None,
    discovery_root: Path | None = None,
    trusted_base: str | None = None,
) -> list[Finding]:
    findings: list[Finding] = []

    def bad(message: str) -> None:
        findings.append(Finding(message))

    if not isinstance(record, dict):
        return [Finding("record: must be a JSON object")]
    if record.get("schema") != SCHEMA_ID:
        bad(f"schema: must be {SCHEMA_ID!r}")

    known = {
        "schema",
        "record_kind",
        "increment",
        "evaluated_at",
        "inventory_source",
        "operations",
        "identities",
        "failure_matrix",
        "concurrency_matrix",
        "fix_reclosure",
        "platform_invariants",
    }
    for key in record:
        # No field may assert that closure was reached: closure is computed.
        if key not in known:
            bad(f"record: unexpected field {key!r} (closure is derived, never declared)")

    kind = record.get("record_kind")
    if kind not in {"initial", "revision"}:
        bad("record_kind: must be 'initial' or 'revision' (a revision may not be implicit)")
    if kind == "revision" and record.get("fix_reclosure") is None:
        bad("record_kind: a revision must declare fix_reclosure")
    if kind == "initial" and record.get("fix_reclosure") is not None:
        bad("record_kind: an initial record may not declare fix_reclosure")
    # record_kind is NOT self-attested: the project-owned lineage ledger says
    # whether this increment already has an accepted record, and which one the
    # next revision must supersede.
    ledger_entries: list[dict[str, Any]] = []
    if discovery_root is not None:
        ledger, ledger_errors = load_authority(
            discovery_root, PROJECT_LINEAGE_LEDGER, {"increments": dict}
        )
        for error in ledger_errors:
            bad(error)
        increment_id = (record.get("increment") or {}).get("increment_id") if isinstance(
            record.get("increment"), dict
        ) else None
        if isinstance(ledger, dict) and text(increment_id):
            increments = ledger.get("increments")
            raw_entries = increments.get(str(increment_id)) if isinstance(increments, dict) else None
            if raw_entries is None:
                raw_entries = []
            if not isinstance(raw_entries, list):
                bad(f"{PROJECT_LINEAGE_LEDGER}: entries for this increment must be a list")
                raw_entries = []
            for position, entry in enumerate(raw_entries):
                where = f"{PROJECT_LINEAGE_LEDGER}[{increment_id}][{position}]"
                if not isinstance(entry, dict):
                    bad(f"{where}: must be an object")
                    continue
                if not text(entry.get("exact_base")):
                    bad(f"{where}.exact_base: required")
                digest = entry.get("sha256")
                if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                    bad(f"{where}.sha256: must be a 64-character hex digest")
                if parse_time(entry.get("evaluated_at")) is None:
                    bad(f"{where}.evaluated_at: timezone-qualified ISO-8601 timestamp required")
                ledger_entries.append(entry)
        if kind == "initial" and ledger_entries:
            bad(
                "record_kind: this increment already has an accepted record in "
                f"{PROJECT_LINEAGE_LEDGER}, so a later record cannot call itself initial"
            )
        if kind == "revision" and not ledger_entries:
            bad(
                f"record_kind: {PROJECT_LINEAGE_LEDGER} has no accepted record for this increment, "
                "so there is nothing to revise"
            )
    increment = record.get("increment")
    if not isinstance(increment, dict) or not all(
        text(increment.get(k)) for k in ("repo", "exact_base", "increment_id")
    ):
        bad("increment: repo, exact_base and increment_id are required")
    if parse_time(record.get("evaluated_at")) is None:
        bad("evaluated_at: timezone-qualified ISO-8601 timestamp required (a naive timestamp is not a fact)")

    if discovery_root is not None:
        # The authority files may not be narrowed inside the increment they
        # govern: their bytes must equal a copy taken from a source independent
        # of this increment (the trusted base). Changing the project surface or
        # the lineage ledger is then its own reviewed change, landed first.
        if not text(trusted_base):
            bad(
                "authority: no trusted base revision was supplied (--trusted-base), so the project "
                "surface and lineage could have been narrowed inside this very increment"
            )
        else:
            resolved, lineage_errors = resolve_trusted_base(discovery_root, str(trusted_base))
            for error in lineage_errors:
                bad(error)
            if resolved is not None:
                for relative in (PROJECT_SURFACE_CONFIG, PROJECT_LINEAGE_LEDGER):
                    live, live_errors = authority_file(discovery_root, relative)
                    for error in live_errors:
                        bad(error)
                    trusted_bytes, git_error = git_blob(discovery_root, resolved, relative)
                    if git_error is not None:
                        # Introduction (the file does not exist at the trusted
                        # base) is not narrowing — but it is only admissible
                        # for a first record of an increment with no accepted
                        # lineage, and it is stated in the output rather than
                        # passed over in silence.
                        introducing = kind == "initial" and not ledger_entries
                        if introducing and "cannot read" in git_error:
                            bad(
                                f"authority-note: {relative} does not exist at the trusted base "
                                f"{resolved[:12]} — accepted ONLY as the increment that introduces it "
                                "(initial record, empty lineage). Every later increment must match the "
                                "committed bytes."
                            )
                        else:
                            bad(f"authority: {git_error}")
                        continue
                    if live is None or trusted_bytes is None:
                        continue
                    if live.read_bytes() != trusted_bytes:
                        bad(
                            f"authority: {relative} differs from the trusted base {resolved[:12]} — "
                            "narrowing the project surface or rewriting lineage must land as its own "
                            "reviewed change, not inside the increment it governs"
                        )
    # ---- operations -----------------------------------------------------
    operations = record.get("operations")
    ops: dict[str, dict[str, Any]] = {}
    if not isinstance(operations, list) or not operations:
        bad("operations: at least one operation is required")
    else:
        for index, op in enumerate(operations):
            where = f"operations[{index}]"
            if not isinstance(op, dict):
                bad(f"{where}: must be an object")
                continue
            op_id = op.get("id")
            if not text(op_id):
                bad(f"{where}.id: required")
                continue
            if op_id in ops:
                bad(f"{where}.id: duplicate operation {op_id!r}")
                continue
            if not text(op.get("source_ref")):
                bad(f"{where}.source_ref: required (derived from the code surface)")
            reads_ok = isinstance(op.get("reads"), list) and all(
                text(i) for i in op.get("reads", [])
            )
            writes_ok = isinstance(op.get("writes"), list) and all(
                text(i) for i in op.get("writes", [])
            )
            if not reads_ok or not writes_ok:
                bad(f"{where}: reads and writes must be identity lists")
            if op.get("kind") not in {"read", "write"}:
                bad(f"{where}.kind: must be 'read' or 'write'")
            if op.get("kind") == "write" and not op.get("writes"):
                bad(f"{where}: a write operation must declare at least one written identity")
            if op.get("kind") == "read" and op.get("writes"):
                bad(f"{where}: a read operation must not declare writes")
            ops[str(op_id)] = op

    # ---- canonical inventory, both directions ---------------------------
    source = record.get("inventory_source")
    # Discovery is PROJECT-OWNED: the gate reads the repository's own surface
    # config, never a scope the record chose. A record author can therefore not
    # shrink the surface they are measured against, and cannot point the walk
    # outside the repository.
    if discovery_root is not None:
        config, config_errors = load_authority(
            discovery_root, PROJECT_SURFACE_CONFIG, {"globs": list, "pattern": str}
        )
        for error in config_errors:
            bad(error)
        if isinstance(config, dict):
            globs = config.get("globs")
            pattern = config.get("pattern")
            if not text_list(globs) or not text(pattern):
                bad(f"{PROJECT_SURFACE_CONFIG}: globs and pattern are required")
            else:
                discovered, errors = discover_operations(discovery_root, globs, str(pattern))
                for error in errors:
                    bad(error)
                if not errors and not discovered:
                    bad(
                        f"{PROJECT_SURFACE_CONFIG}: the project surface config found no operation — "
                        "a discovery that matches nothing proves nothing"
                    )
                for missing in sorted(discovered - set(ops)):
                    bad(f"operations: {missing!r} exists in the project code surface but is not modelled")
                for extra in sorted(set(ops) - discovered):
                    bad(f"operations: {extra!r} is modelled but does not exist in the project code surface")
    if not isinstance(source, dict) or not text(source.get("ref")) or not text(
        source.get("sha256")
    ):
        bad("inventory_source: ref and sha256 of the EXTERNAL canonical inventory are required")
    elif inventory_path is not None and str(source.get("ref")) != inventory_path:
        bad(
            f"inventory_source.ref: the record names {source.get('ref')!r} but the inventory supplied "
            f"was {inventory_path!r} — a canonical reference that is not the file actually checked "
            "proves nothing"
        )
    elif inventory is None:
        bad(
            "inventory_source: the external inventory was not supplied (--inventory), so operation "
            "coverage cannot be checked — a list inside the record can be trimmed alongside it"
        )
    else:
        canonical = set(inventory)
        declared = set(ops)
        for missing in sorted(canonical - declared):
            bad(f"operations: {missing!r} exists in the canonical inventory but is not modelled")
        for extra in sorted(declared - canonical):
            bad(f"operations: {extra!r} is modelled but absent from the canonical inventory")

    # ---- identities -----------------------------------------------------
    identities: dict[str, dict[str, Any]] = {}
    id_rows = record.get("identities")
    if not isinstance(id_rows, list) or not id_rows:
        bad("identities: at least one identity row is required")
    else:
        for index, row in enumerate(id_rows):
            where = f"identities[{index}]"
            if not isinstance(row, dict):
                bad(f"{where}: must be an object")
                continue
            ident = row.get("id")
            if not text(ident):
                bad(f"{where}.id: required")
                continue
            if str(ident) in identities:
                bad(
                    f"{where}.id: duplicate identity {ident!r} — a second definition silently "
                    "overwrites the first, so the state machine would not be unique"
                )
                continue
            if row.get("scope") not in {"persisted", "client"}:
                bad(f"{where}.scope: must be 'persisted' or 'client'")
            if not text(row.get("owner")):
                bad(f"{where}.owner: required")
            if not text_list(row.get("states"), minimum=2):
                bad(f"{where}.states: at least two states are required")
            transitions = row.get("transitions")
            if not isinstance(transitions, list) or not transitions:
                bad(f"{where}.transitions: required")
            else:
                states = set(row.get("states") or [])
                for t_index, transition in enumerate(transitions):
                    t_where = f"{where}.transitions[{t_index}]"
                    if not isinstance(transition, dict) or not all(
                        text(transition.get(k)) for k in ("from", "to", "trigger")
                    ):
                        bad(f"{t_where}: from, to and trigger are required")
                        continue
                    for endpoint in ("from", "to"):
                        if transition[endpoint] not in states:
                            bad(f"{t_where}.{endpoint}: {transition[endpoint]!r} is not a declared state")
            if not text_list(row.get("cleared_by")):
                bad(f"{where}.cleared_by: required (who may clear this identity)")
            if not text(row.get("generation_binding")):
                bad(f"{where}.generation_binding: required (state 'none' with a reason if unbound)")
            identities[str(ident)] = row

    for op_id, op in ops.items():
        for ident in list(op.get("reads", [])) + list(op.get("writes", [])):
            if ident not in identities:
                bad(f"operations[{op_id}]: identity {ident!r} has no identity row")

    # ---- failure / uncertainty matrix -----------------------------------
    writes = {op_id for op_id, op in ops.items() if op.get("kind") == "write"}
    failure_rows: dict[str, dict[str, Any]] = {}
    rows = record.get("failure_matrix")
    if not isinstance(rows, list):
        bad("failure_matrix: required")
    else:
        for index, row in enumerate(rows):
            where = f"failure_matrix[{index}]"
            if not isinstance(row, dict) or not text(row.get("operation")):
                bad(f"{where}.operation: required")
                continue
            op_id = str(row["operation"])
            if op_id in failure_rows:
                bad(f"{where}: duplicate row for {op_id!r}")
            failure_rows[op_id] = row
            if op_id not in writes:
                bad(f"{where}: {op_id!r} is not a declared write operation")
            for field in ("success", "failure", "unknown", "peer_observes", "reclaimer", "residue_discoverable_by"):
                if not text(row.get(field)):
                    bad(f"{where}.{field}: required (an empty cell is the finding you have not received yet)")
    for op_id in sorted(writes - set(failure_rows)):
        bad(f"failure_matrix: no row for write operation {op_id!r}")

    # ---- concurrency matrix: the cross product --------------------------
    expected = {pair_key(a, b) for a, b in itertools.combinations_with_replacement(sorted(ops), 2)}
    cells: dict[tuple[str, str], dict[str, Any]] = {}
    matrix = record.get("concurrency_matrix")
    if not isinstance(matrix, list):
        bad("concurrency_matrix: required")
    else:
        for index, cell in enumerate(matrix):
            where = f"concurrency_matrix[{index}]"
            if not isinstance(cell, dict):
                bad(f"{where}: must be an object")
                continue
            pair = cell.get("pair")
            if not (isinstance(pair, list) and len(pair) == 2 and all(text(p) for p in pair)):
                bad(f"{where}.pair: two operation ids are required")
                continue
            key = pair_key(str(pair[0]), str(pair[1]))
            if key in cells:
                bad(f"{where}: duplicate cell for {key[0]!r} x {key[1]!r}")
            cells[key] = cell
            if key not in expected:
                bad(f"{where}: {key[0]!r} x {key[1]!r} is not a pair of declared operations")
                continue
            disposition = cell.get("disposition")
            if disposition not in PAIR_DISPOSITIONS:
                bad(f"{where}.disposition: must be one of {sorted(PAIR_DISPOSITIONS)}")
                continue
            write_write, read_write = hazards(ops[key[0]], ops[key[1]])
            if disposition == "serialized":
                if not (write_write or read_write):
                    bad(
                        f"{where}: declared serialized while the operations share no hazard — "
                        "needless serialization is not a safe default"
                    )
                point = cell.get("serialization_point")
                if not isinstance(point, dict) or not text(point.get("object")):
                    bad(f"{where}.serialization_point.object: required for a serialized pair")
                else:
                    # DERIVED, not attested: the named object must be an identity
                    # that BOTH sides actually read and write.
                    obj = str(point["object"])
                    both_rw = [
                        op_id
                        for op_id in key
                        if obj in set(ops[op_id].get("reads", []))
                        and obj in set(ops[op_id].get("writes", []))
                    ]
                    if obj not in identities:
                        bad(
                            f"{where}.serialization_point.object: {obj!r} is not a declared identity — "
                            "a serialization point is a modelled object, not a name"
                        )
                    elif len(both_rw) != 2:
                        missing = [op_id for op_id in key if op_id not in both_rw]
                        bad(
                            f"{where}.serialization_point.object: {obj!r} is not read AND written by "
                            f"{missing} — two writers that share no read-and-written object serialize on nothing"
                        )
                if not text(cell.get("loser_outcome")):
                    bad(f"{where}.loser_outcome: required for a serialized pair")
                if not text_list(cell.get("both_orders_tested"), minimum=2):
                    bad(f"{where}.both_orders_tested: a test reference for EACH commit order is required")
            elif disposition == "impossible":
                imp = cell.get("impossibility")
                if not isinstance(imp, dict) or imp.get("kind") not in IMPOSSIBILITY_KINDS:
                    bad(
                        f"{where}.impossibility.kind: must be a system property "
                        f"{sorted(IMPOSSIBILITY_KINDS)} — timing or UI flow is not one, and a disjoint "
                        "keyspace is a SAFE OVERLAP, not an impossibility"
                    )
                elif not text(imp.get("evidence")):
                    bad(f"{where}.impossibility.evidence: required")
            elif disposition == "read_only_snapshot":
                # Legal over a read/write hazard, with the staleness contract
                # spelled out. Not legal when both sides write the same state.
                if write_write:
                    bad(
                        f"{where}: declared read-only while both operations WRITE {sorted(write_write)}"
                    )
                contract = cell.get("snapshot_contract")
                if not isinstance(contract, dict) or not all(
                    text(contract.get(field)) for field in ("consistency", "generation", "staleness")
                ):
                    bad(
                        f"{where}.snapshot_contract: consistency, generation and staleness are required "
                        "for a snapshot read over a concurrent writer"
                    )
            elif disposition == "commutative":
                if not write_write:
                    bad(
                        f"{where}: commutativity is a property of two WRITES to the same state; this "
                        "pair has no write/write hazard"
                    )
                if not text(cell.get("commutativity_evidence")):
                    bad(f"{where}.commutativity_evidence: required")
                if not text_list(cell.get("idempotence_tested"), minimum=2):
                    bad(
                        f"{where}.idempotence_tested: a test reference for EACH application order is "
                        "required to claim commutativity"
                    )
            elif disposition == "disjoint_keyspace":
                partition = cell.get("key_partition")
                overlap = write_write | read_write
                if not isinstance(partition, dict):
                    bad(f"{where}.key_partition: required for a disjoint-keyspace pair")
                else:
                    if overlap and partition.get("identity") not in overlap:
                        bad(
                            f"{where}.key_partition.identity: must partition an overlapping identity "
                            f"{sorted(overlap)}"
                        )
                    left, right = partition.get("predicate_a"), partition.get("predicate_b")
                    if not text(left) or not text(right):
                        bad(f"{where}.key_partition: predicate_a and predicate_b are required")
                    elif left == right:
                        bad(f"{where}.key_partition: the predicates are identical, so the keyspaces are not disjoint")
                    if not text(partition.get("evidence")):
                        bad(f"{where}.key_partition.evidence: required")
    for key in sorted(expected - set(cells)):
        bad(
            f"concurrency_matrix: missing cell {key[0]!r} x {key[1]!r} — the matrix is the cross "
            "product of the operation inventory, not a hand-listed subset"
        )

    # ---- fix-induced re-closure, derived from a versioned diff ----------
    # The change surface itself is derived: comparing this record with the
    # base version catches a changed write set, a rewritten UNKNOWN cell, a
    # swapped disposition or a moved serialization point — none of which a
    # "this fix touches X" declaration would have mentioned.
    fix = record.get("fix_reclosure")
    if fix is None and base is not None:
        # Omitting the declaration must not skip the diff: a record that
        # changed at all owes a re-closure entry.
        bad(
            "fix_reclosure: a base record was supplied, so this record is a revision and must declare "
            "the fix that produced it (omitting the declaration cannot bypass the diff)"
        )
    if fix is not None:
        if not isinstance(fix, dict):
            bad("fix_reclosure: must be an object")
        elif not text(fix.get("fix_id")) or not text(fix.get("base_record_ref")) or not text(
            fix.get("base_record_sha256")
        ):
            bad("fix_reclosure: fix_id, base_record_ref and base_record_sha256 are required")
        elif parse_time(fix.get("introduced_at")) is None:
            bad("fix_reclosure.introduced_at: timezone-qualified ISO-8601 timestamp required")
        elif base_path is not None and str(fix.get("base_record_ref")) != base_path:
            bad(
                f"fix_reclosure.base_record_ref: the record names {fix.get('base_record_ref')!r} but "
                f"the base supplied was {base_path!r} — a predecessor reference that is not the file "
                "actually diffed proves nothing"
            )
        elif base is None:
            bad(
                "fix_reclosure: the base record was not supplied (--base), so the changed surface "
                "cannot be derived and re-closure cannot be checked"
            )
        elif not isinstance(base, dict):
            bad("fix_reclosure: the supplied base record is not an object")
        else:
            introduced_at = parse_time(fix.get("introduced_at"))
            # The base must be THIS record's predecessor, not any well-formed
            # record: a foreign base would silently empty the change surface.
            base_increment = base.get("increment") if isinstance(base.get("increment"), dict) else {}
            own_increment = increment if isinstance(increment, dict) else {}
            if ledger_entries:
                last = ledger_entries[-1]
                if fix.get("base_record_sha256") != last.get("sha256"):
                    bad(
                        "fix_reclosure.base_record_sha256: must supersede the last accepted record "
                        f"for this increment ({last.get('sha256')!r} per {PROJECT_LINEAGE_LEDGER}) — "
                        "a synthetic predecessor is not lineage"
                    )
                if fix.get("base_exact_base") != last.get("exact_base"):
                    bad(
                        "fix_reclosure.base_exact_base: must be the exact_base of the last accepted "
                        f"record ({last.get('exact_base')!r} per {PROJECT_LINEAGE_LEDGER})"
                    )
            declared_base_exact = fix.get("base_exact_base")
            if not text(declared_base_exact):
                bad("fix_reclosure.base_exact_base: required (the revision this record supersedes)")
            elif base_increment.get("exact_base") != declared_base_exact:
                bad(
                    "fix_reclosure.base_exact_base: the supplied base is at "
                    f"{base_increment.get('exact_base')!r}, not the declared {declared_base_exact!r}"
                )
            elif own_increment.get("exact_base") == declared_base_exact:
                bad(
                    "fix_reclosure.base_exact_base: this record declares the SAME exact_base as its "
                    "base — a revision that supersedes nothing is not a fix"
                )
            for field in ("repo", "increment_id"):
                if base_increment.get(field) != own_increment.get(field):
                    bad(
                        f"fix_reclosure: the supplied base belongs to a different {field} "
                        f"({base_increment.get(field)!r} vs {own_increment.get(field)!r})"
                    )
            base_at = parse_time(base.get("evaluated_at"))
            own_at = parse_time(record.get("evaluated_at"))
            if base_at is None:
                bad("fix_reclosure: the supplied base has no usable evaluated_at")
            elif own_at is not None and base_at >= own_at:
                bad(
                    "fix_reclosure: the supplied base is not a predecessor "
                    "(its evaluated_at is not earlier than this record's)"
                )
            CONTRACT_TABLES = (
                "inventory_source",
                "operations",
                "identities",
                "failure_matrix",
                "concurrency_matrix",
                "platform_invariants",
            )

            def contract_only(value: Any) -> Any:
                """The contract surface, without re-validation bookkeeping."""
                if isinstance(value, dict):
                    return {k: contract_only(v) for k, v in sorted(value.items()) if k != "revalidated"}
                if isinstance(value, list):
                    return [contract_only(v) for v in value]
                return value

            surface = {table: contract_only(record.get(table)) for table in CONTRACT_TABLES}
            base_surface = {table: contract_only(base.get(table)) for table in CONTRACT_TABLES}
            if surface == base_surface:
                bad(
                    "fix_reclosure: this record is byte-equivalent to its base apart from timestamps — "
                    "a backdated copy is not a predecessor, and there is no change to re-close"
                )
            base_ops = {
                str(op.get("id")): op
                for op in base.get("operations", [])
                if isinstance(op, dict) and text(op.get("id"))
            }
            base_ids = {
                str(row.get("id")): row
                for row in base.get("identities", [])
                if isinstance(row, dict) and text(row.get("id"))
            }
            base_rows = {
                str(row.get("operation")): row
                for row in base.get("failure_matrix", [])
                if isinstance(row, dict) and text(row.get("operation"))
            }
            base_cells: dict[tuple[str, str], dict[str, Any]] = {}
            for cell in base.get("concurrency_matrix", []):
                pair = cell.get("pair") if isinstance(cell, dict) else None
                if isinstance(pair, list) and len(pair) == 2 and all(text(p) for p in pair):
                    base_cells[pair_key(str(pair[0]), str(pair[1]))] = cell

            def stripped(value: Any) -> Any:
                """Compare contract content, not re-validation bookkeeping."""
                if isinstance(value, dict):
                    return {k: stripped(v) for k, v in sorted(value.items()) if k != "revalidated"}
                if isinstance(value, list):
                    return [stripped(v) for v in value]
                return value

            changed_identities = {
                ident
                for ident in set(identities) | set(base_ids)
                if stripped(identities.get(ident)) != stripped(base_ids.get(ident))
            }
            changed_ops = {
                op_id
                for op_id in set(ops) | set(base_ops)
                if stripped(ops.get(op_id)) != stripped(base_ops.get(op_id))
            }
            changed_rows = {
                op_id
                for op_id in set(failure_rows) | set(base_rows)
                if stripped(failure_rows.get(op_id)) != stripped(base_rows.get(op_id))
            }
            changed_cells = {
                key
                for key in set(cells) | set(base_cells)
                if stripped(cells.get(key)) != stripped(base_cells.get(key))
            }
            if stripped(record.get("platform_invariants")) != stripped(base.get("platform_invariants")):
                # A changed platform assumption can invalidate every cell that
                # relied on it, so the whole matrix is back in scope.
                changed_ops |= set(ops)

            affected_ops = set(changed_ops) | set(changed_rows)
            affected_ops |= {
                op_id
                for op_id, op in ops.items()
                if changed_identities & (set(op.get("reads", [])) | set(op.get("writes", [])))
            }
            for key in changed_cells:
                affected_ops |= {key[0], key[1]} & set(ops)

            affected_cells = {
                key for key in cells if key[0] in affected_ops or key[1] in affected_ops
            } | (changed_cells & set(cells))
            affected_rows = (affected_ops | changed_rows) & set(failure_rows)

            def fresh(container: Any, label: str) -> None:
                revalidated = container.get("revalidated") if isinstance(container, dict) else None
                entry = None
                if isinstance(revalidated, list):
                    entry = next(
                        (
                            r
                            for r in revalidated
                            if isinstance(r, dict) and r.get("fix_id") == fix.get("fix_id")
                        ),
                        None,
                    )
                if entry is None:
                    bad(
                        f"fix_reclosure: {label} is reachable from the derived change surface but "
                        "carries no re-validation for this fix"
                    )
                    return
                when = parse_time(entry.get("at"))
                if when is None or (introduced_at is not None and when < introduced_at):
                    bad(
                        f"fix_reclosure: re-validation of {label} is stale "
                        "(it predates the fix that re-opened it)"
                    )
                if not text_list(entry.get("evidence")):
                    bad(f"fix_reclosure: re-validation of {label} has no evidence")

            for key in sorted(affected_cells):
                fresh(cells.get(key, {}), f"cell {key[0]!r} x {key[1]!r}")
            for op_id in sorted(affected_rows):
                fresh(failure_rows.get(op_id, {}), f"failure row {op_id!r}")

    # ---- platform invariants -------------------------------------------
    invariants = record.get("platform_invariants")
    if not isinstance(invariants, list) or not invariants:
        bad("platform_invariants: list the platform rules the design relies on, with where each is verified")
    else:
        for index, inv in enumerate(invariants):
            where = f"platform_invariants[{index}]"
            if not isinstance(inv, dict) or not text(inv.get("rule")) or not text(inv.get("verified_by")):
                bad(f"{where}: rule and verified_by are required")

    return findings


def sample_record() -> dict[str, Any]:
    """A minimal record that passes: two operations, one real conflict."""
    return {
        "schema": SCHEMA_ID,
        "record_kind": "initial",
        "increment": {
            "repo": "bonginkan/example",
            "exact_base": "0000000000000000000000000000000000000000",
            "increment_id": "attachment-upload-initial",
        },
        "evaluated_at": "2026-07-28T00:00:00+00:00",
        "inventory_source": {
            "kind": "route_manifest",
            "ref": "examples/implementation-contract-closure.inventory.txt",
            "sha256": "ee9da3358374da37b3f088e00cd2b3b4adc2295f8015f8894c6ed0d9c18dbbee",
        },
        "operations": [
            {
                "id": "upload",
                "kind": "write",
                "source_ref": "app/api/attachments/route.ts:POST",
                "reads": ["attachment", "draft_envelope"],
                "writes": ["attachment", "draft_envelope"],
            },
            {
                "id": "remove",
                "kind": "write",
                "source_ref": "app/api/attachments/[id]/route.ts:DELETE",
                "reads": ["attachment", "draft_envelope"],
                "writes": ["attachment", "draft_envelope"],
            },
            {
                "id": "list",
                "kind": "read",
                "source_ref": "app/api/attachments/route.ts:GET",
                "reads": ["attachment"],
                "writes": [],
            },
        ],
        "identities": [
            {
                "id": "attachment",
                "scope": "persisted",
                "owner": "session owner",
                "states": ["draft", "sent", "deleting"],
                "transitions": [
                    {"from": "draft", "to": "sent", "trigger": "send transaction"},
                    {"from": "draft", "to": "deleting", "trigger": "owner delete"},
                ],
                "cleared_by": ["owner delete", "stale reaper"],
                "generation_binding": "upload key (deterministic document id)",
            },
            {
                "id": "draft_envelope",
                "scope": "persisted",
                "owner": "session owner",
                "states": ["open", "sent", "deleting"],
                "transitions": [
                    {"from": "open", "to": "sent", "trigger": "send transaction"},
                    {"from": "open", "to": "deleting", "trigger": "stale reaper"},
                ],
                "cleared_by": ["stale reaper"],
                "generation_binding": "composer draft key",
            },
        ],
        "failure_matrix": [
            {
                "operation": "upload",
                "success": "record committed and counted",
                "failure": "nothing stored; object rolled back",
                "unknown": "commit outcome unknown: object kept, record re-read",
                "peer_observes": "either the committed record or nothing",
                "reclaimer": "storage-origin reaper",
                "residue_discoverable_by": "object path carries its record coordinates",
            },
            {
                "operation": "remove",
                "success": "bytes deleted, then record deleted",
                "failure": "record stays in deleting; caller sees a retryable error",
                "unknown": "same as failure: the record stays until confirmed",
                "peer_observes": "the attachment as deleting, never as draft-without-bytes",
                "reclaimer": "deleting-state reaper",
                "residue_discoverable_by": "collection-group scan on status",
            },
        ],
        "concurrency_matrix": [
            {
                "pair": ["upload", "upload"],
                "disposition": "serialized",
                "serialization_point": {"object": "draft_envelope"},
                "loser_outcome": "cap rejection, object removed",
                "both_orders_tested": ["races: cap A-then-B", "races: cap B-then-A"],
            },
            {
                "pair": ["remove", "upload"],
                "disposition": "serialized",
                "serialization_point": {"object": "attachment"},
                "loser_outcome": "upload commits nothing; removal wins",
                "both_orders_tested": ["races: delete-then-commit", "races: commit-then-delete"],
            },
            {
                "pair": ["remove", "remove"],
                "disposition": "serialized",
                "serialization_point": {"object": "attachment"},
                "loser_outcome": "second delete is idempotent",
                "both_orders_tested": ["races: delete retry A", "races: delete retry B"],
            },
            {
                "pair": ["list", "list"],
                "disposition": "read_only_snapshot",
                "snapshot_contract": {
                    "consistency": "each read is a single-query snapshot",
                    "generation": "response carries the read generation it applies to",
                    "staleness": "a listing may omit an attachment committed after its snapshot",
                },
            },
            {
                "pair": ["list", "upload"],
                "disposition": "read_only_snapshot",
                "snapshot_contract": {
                    "consistency": "single-query snapshot",
                    "generation": "the read generation is returned with the listing",
                    "staleness": "a listing may omit an attachment committed after its snapshot",
                },
            },
            {
                "pair": ["list", "remove"],
                "disposition": "read_only_snapshot",
                "snapshot_contract": {
                    "consistency": "single-query snapshot",
                    "generation": "the read generation is returned with the listing",
                    "staleness": "a listing may still show an attachment that is already deleting",
                },
            },
        ],
        "platform_invariants": [
            {
                "rule": "a transaction may not read after it writes",
                "verified_by": "vendor transaction documentation + fake enforcing the rule in tests",
            }
        ],
    }


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schemas" / "implementation-contract-closure.schema.json"
#: Selftest trust anchor: HEAD~1 is an immutable ancestor object, never the
#: working tree, so the controls exercise the real provenance path.
TRUSTED_BASE = "HEAD~1"
CONTROL_COUNT = 61


def selftest_repo(tmp: Path) -> Path | None:
    """A throwaway two-commit repository, so the provenance controls exercise
    real Git objects instead of assuming the checkout they run in."""
    import subprocess

    root = tmp / "repo"
    (root / ".fairy").mkdir(parents=True)
    (root / "fixtures" / "implementation-contract-closure" / "surface").mkdir(parents=True)
    source = Path(__file__).resolve().parents[1]
    for relative in (
        PROJECT_SURFACE_CONFIG,
        PROJECT_LINEAGE_LEDGER,
        "fixtures/implementation-contract-closure/surface/upload.ts",
        "fixtures/implementation-contract-closure/surface/remove.ts",
        "fixtures/implementation-contract-closure/surface/list.ts",
    ):
        (root / relative).write_bytes((source / relative).read_bytes())
    env = {
        "GIT_AUTHOR_NAME": "selftest",
        "GIT_AUTHOR_EMAIL": "selftest@example.invalid",
        "GIT_COMMITTER_NAME": "selftest",
        "GIT_COMMITTER_EMAIL": "selftest@example.invalid",
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(tmp),
    }

    def git(*args: str) -> int:
        return subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, env=env
        ).returncode

    try:
        if git("init", "-q") != 0:
            return None
    except FileNotFoundError:
        return None
    git("add", "-A")
    git("commit", "-q", "-m", "authority base")
    (root / "README.md").write_text("second commit\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "work")
    return root


def run_selftest() -> int:
    failures: list[str] = []

    def check(condition: bool, label: str) -> None:
        if not condition:
            failures.append(label)

    inventory = ["upload", "remove", "list"]
    inventory_path = "examples/implementation-contract-closure.inventory.txt"
    provenance_dir = tempfile.TemporaryDirectory()
    REPO_ROOT_LOCAL = selftest_repo(Path(provenance_dir.name)) or REPO_ROOT
    TRUSTED = "HEAD~1" if REPO_ROOT_LOCAL is not REPO_ROOT else None

    def blocked(
        record: dict[str, Any],
        fragment: str,
        label: str,
        base: Any = None,
        ops: Iterable[str] | None = None,
        path: str | None = inventory_path,
        base_path: str | None = "previous",
    ) -> None:
        found = validate_record(
            record,
            base,
            inventory if ops is None else ops,
            path,
            base_path,
            REPO_ROOT_LOCAL,
            TRUSTED,
        )
        check(
            any(fragment in str(f) for f in found),
            f"{label}: expected a finding containing {fragment!r}, got {[str(f) for f in found]!r}",
        )

    base = sample_record()
    check(
        validate_record(base, None, inventory, inventory_path, None, REPO_ROOT_LOCAL, TRUSTED) == [],
        f"sample must validate: {[str(f) for f in validate_record(base, None, inventory, inventory_path, None, REPO_ROOT_LOCAL, TRUSTED)]}",
    )

    # Hostile: an empty contract must never pass.
    empty = {"schema": SCHEMA_ID}
    check(len(validate_record(empty, None, inventory, inventory_path, None, REPO_ROOT_LOCAL, TRUSTED)) >= 5, "an empty record must produce multiple findings")

    # Hostile: a hand-listed subset of the cross product.
    subset = json.loads(json.dumps(base))
    subset["concurrency_matrix"] = [
        cell for cell in subset["concurrency_matrix"] if cell["pair"] != ["remove", "upload"]
    ]
    blocked(subset, "missing cell", "omitted pair")

    # Hostile: a serialized pair whose point is written by only one side.
    one_sided = json.loads(json.dumps(base))
    one_sided["operations"][1]["reads"] = ["draft_envelope"]  # remove reads the attachment no more
    one_sided["concurrency_matrix"][1]["serialization_point"] = {"object": "attachment"}
    blocked(one_sided, "is not read AND written by", "one-sided serialization point")

    # Hostile: only one commit order tested.
    single_order = json.loads(json.dumps(base))
    single_order["concurrency_matrix"][0]["both_orders_tested"] = ["one order only"]
    blocked(single_order, "both_orders_tested", "single commit order")

    # Hostile: claiming safety while the sets conflict.
    over_claimed = json.loads(json.dumps(base))
    over_claimed["concurrency_matrix"][1] = {"pair": ["remove", "upload"], "disposition": "read_only_snapshot"}
    blocked(over_claimed, "declared read-only while both operations WRITE", "over-claimed safety")

    # Hostile: timing excuse dressed as impossibility.
    timing = json.loads(json.dumps(base))
    timing["concurrency_matrix"][1] = {
        "pair": ["remove", "upload"],
        "disposition": "impossible",
        "impossibility": {"kind": "ui_never_issues_both", "evidence": "the UI disables the button"},
    }
    blocked(timing, "must be a system property", "timing excuse")

    # Safe overlaps must NOT be over-blocked: read x read passes with no point.
    check(
        not any("list' x 'list" in str(f) for f in validate_record(base, None, inventory, inventory_path, None, REPO_ROOT_LOCAL, TRUSTED)),
        "a read-only pair must not be forced to serialize",
    )

    # disjoint_keyspace is a safe overlap, not an impossibility.
    disjoint = json.loads(json.dumps(base))
    disjoint["concurrency_matrix"][1] = {
        "pair": ["remove", "upload"],
        "disposition": "disjoint_keyspace",
        "key_partition": {
            "identity": "attachment",
            "predicate_a": "attachment id < midpoint",
            "predicate_b": "attachment id >= midpoint",
            "evidence": "ids are assigned from disjoint ranges per client",
        },
    }
    check(
        validate_record(disjoint, None, inventory, inventory_path, None, REPO_ROOT_LOCAL, TRUSTED) == [],
        f"a declared disjoint keyspace with evidence must pass: {[str(f) for f in validate_record(disjoint, None, inventory, inventory_path, None, REPO_ROOT_LOCAL, TRUSTED)]}",
    )
    same_predicate = json.loads(json.dumps(disjoint))
    same_predicate["concurrency_matrix"][1]["key_partition"]["predicate_b"] = "attachment id < midpoint"
    blocked(same_predicate, "predicates are identical", "fake partition")

    # Hostile: an operation the canonical inventory has but the record omits.
    omitted = json.loads(json.dumps(base))
    omitted["operations"] = [op for op in omitted["operations"] if op["id"] != "list"]
    blocked(omitted, "exists in the canonical inventory but is not modelled", "inventory omission")

    blocked(
        base,
        "absent from the canonical inventory",
        "invented operation",
        None,
        ["upload", "remove"],
    )

    # Hostile: a blank uncertainty cell.
    blank = json.loads(json.dumps(base))
    blank["failure_matrix"][0]["unknown"] = ""
    blocked(blank, "failure_matrix[0].unknown", "blank uncertainty cell")

    # Hostile: a write with no reclaimer for its residue.
    residue = json.loads(json.dumps(base))
    residue["failure_matrix"][1]["reclaimer"] = "  "
    blocked(residue, "reclaimer", "missing reclaimer")

    # Snapshot reads over a concurrent writer are legal, WITH a contract.
    snapshot = json.loads(json.dumps(base))
    snapshot["concurrency_matrix"][4] = {
        "pair": ["list", "upload"],
        "disposition": "read_only_snapshot",
        "snapshot_contract": {
            "consistency": "single-query snapshot",
            "generation": "read generation returned to the caller",
            "staleness": "may omit a concurrently committed attachment",
        },
    }
    check(
        validate_record(snapshot, None, inventory, inventory_path, None, REPO_ROOT_LOCAL, TRUSTED) == [],
        f"a snapshot read must not be forced to serialize: {[str(f) for f in validate_record(snapshot, None, inventory, inventory_path, None, REPO_ROOT_LOCAL, TRUSTED)]}",
    )
    no_contract = json.loads(json.dumps(snapshot))
    del no_contract["concurrency_matrix"][4]["snapshot_contract"]
    blocked(no_contract, "snapshot_contract", "snapshot read without a staleness contract")

    # Commutativity needs its own proof obligation.
    commutative = json.loads(json.dumps(base))
    commutative["concurrency_matrix"][0] = {
        "pair": ["upload", "upload"],
        "disposition": "commutative",
        "commutativity_evidence": "both apply the same set union",
        "idempotence_tested": ["races: A then B", "races: B then A"],
    }
    check(
        validate_record(commutative, None, inventory, inventory_path, None, REPO_ROOT_LOCAL, TRUSTED) == [],
        f"a commutative write pair with tests must pass: {[str(f) for f in validate_record(commutative, None, inventory, inventory_path, None, REPO_ROOT_LOCAL, TRUSTED)]}",
    )
    unproven = json.loads(json.dumps(commutative))
    unproven["concurrency_matrix"][0]["idempotence_tested"] = ["only one order"]
    blocked(unproven, "idempotence_tested", "commutativity without both orders")

    # Fix re-closure is derived from the versioned diff, not declared.
    previous = json.loads(json.dumps(base))
    previous["increment"]["increment_id"] = "attachment-upload"
    changed = json.loads(json.dumps(base))
    # A silent change to an existing write set: no declaration mentions it.
    changed["operations"][1]["writes"] = ["attachment", "draft_envelope", "audit_log"]
    changed["identities"].append(
        {
            "id": "audit_log",
            "scope": "persisted",
            "owner": "system",
            "states": ["absent", "written"],
            "transitions": [{"from": "absent", "to": "written", "trigger": "removal"}],
            "cleared_by": ["retention job"],
            "generation_binding": "none: append-only log",
        }
    )
    changed["evaluated_at"] = "2026-07-28T03:00:00+00:00"
    changed["record_kind"] = "revision"
    changed["increment"]["increment_id"] = "attachment-upload"
    changed["increment"]["exact_base"] = "1" * 40
    changed["fix_reclosure"] = {
        "fix_id": "fix-10",
        "introduced_at": "2026-07-28T01:00:00+00:00",
        "base_record_ref": "previous",
        "base_record_sha256": "0" * 64,
        "base_exact_base": "0" * 40,
    }
    findings_without_base = validate_record(changed, None, inventory, inventory_path, 'previous', REPO_ROOT_LOCAL, TRUSTED)
    check(
        any("base record was not supplied" in str(f) for f in findings_without_base),
        "re-closure without the base record must fail closed",
    )
    blocked_pairs = [str(f) for f in validate_record(changed, previous, inventory, inventory_path, 'previous', REPO_ROOT_LOCAL, TRUSTED)]
    check(
        any("carries no re-validation for this fix" in f for f in blocked_pairs),
        f"a derived change surface must demand re-validation: {blocked_pairs!r}",
    )

    revalidated = json.loads(json.dumps(changed))
    revalidated["evaluated_at"] = "2026-07-28T03:00:00+00:00"
    stamp = {"fix_id": "fix-10", "at": "2026-07-28T02:00:00+00:00", "evidence": ["races: both orders"]}
    for cell in revalidated["concurrency_matrix"]:
        cell["revalidated"] = [dict(stamp)]
    for row in revalidated["failure_matrix"]:
        row["revalidated"] = [dict(stamp)]
    check(
        validate_record(revalidated, previous, inventory, inventory_path, 'previous', REPO_ROOT_LOCAL, TRUSTED) == [],
        f"a fully re-closed record must pass: {[str(f) for f in validate_record(revalidated, previous, inventory, inventory_path, 'previous', REPO_ROOT_LOCAL, TRUSTED)]}",
    )

    stale = json.loads(json.dumps(revalidated))
    for cell in stale["concurrency_matrix"]:
        cell["revalidated"] = [
            {"fix_id": "fix-10", "at": "2026-07-27T00:00:00+00:00", "evidence": ["old test"]}
        ]
    blocked_stale = [str(f) for f in validate_record(stale, previous, inventory, inventory_path, 'previous', REPO_ROOT_LOCAL, TRUSTED)]
    check(any("stale" in f for f in blocked_stale), "re-validation predating the fix must be rejected")

    # Hostile: a serialization point that neither side reads AND writes.
    unrelated = json.loads(json.dumps(base))
    unrelated["concurrency_matrix"][0]["serialization_point"] = {"object": "attachment"}
    # upload x upload DOES read+write attachment, so pick a genuinely unrelated one:
    unrelated["identities"].append(
        {
            "id": "unrelated_doc",
            "scope": "persisted",
            "owner": "system",
            "states": ["a", "b"],
            "transitions": [{"from": "a", "to": "b", "trigger": "n/a"}],
            "cleared_by": ["n/a"],
            "generation_binding": "none: unrelated",
        }
    )
    unrelated["concurrency_matrix"][0]["serialization_point"] = {"object": "unrelated_doc"}
    blocked(unrelated, "is not read AND written by", "unrelated serialization object")

    # Hostile: forcing serialization on a hazard-free pair.
    forced = json.loads(json.dumps(base))
    forced["concurrency_matrix"][3] = {
        "pair": ["list", "list"],
        "disposition": "serialized",
        "serialization_point": {"object": "attachment"},
        "loser_outcome": "n/a",
        "both_orders_tested": ["a", "b"],
    }
    blocked(forced, "share no hazard", "needless serialization")

    # Hostile: commutativity claimed for a read/write-only pair.
    misclaimed = json.loads(json.dumps(base))
    misclaimed["concurrency_matrix"][4] = {
        "pair": ["list", "upload"],
        "disposition": "commutative",
        "commutativity_evidence": "reads commute with writes",
        "idempotence_tested": ["a", "b"],
    }
    blocked(misclaimed, "no write/write hazard", "commutativity without two writers")

    # Hostile: the inventory is external, so trimming the record cannot launder it.
    laundered = json.loads(json.dumps(base))
    laundered["operations"] = [op for op in laundered["operations"] if op["id"] != "list"]
    laundered["concurrency_matrix"] = [
        cell for cell in laundered["concurrency_matrix"] if "list" not in cell["pair"]
    ]
    blocked(laundered, "exists in the canonical inventory but is not modelled", "joint omission")

    # Hostile: mixed naive/aware timestamps must be a finding, never a traceback.
    mixed = json.loads(json.dumps(base))
    mixed["record_kind"] = "revision"
    mixed["increment"]["increment_id"] = "attachment-upload"
    mixed["evaluated_at"] = "2026-07-28T00:00:00"
    mixed_previous = json.loads(json.dumps(base))
    mixed_previous["evaluated_at"] = "2026-07-27T00:00:00+00:00"
    mixed["fix_reclosure"] = {
        "fix_id": "fix-tz",
        "introduced_at": "2026-07-27T12:00:00",
        "base_record_ref": "previous",
        "base_record_sha256": "0" * 64,
        "base_exact_base": "0" * 40,
    }
    try:
        tz_findings = validate_record(mixed, mixed_previous, inventory, inventory_path, 'previous', REPO_ROOT_LOCAL, TRUSTED)
    except TypeError as error:  # pragma: no cover - the control exists to prevent this
        tz_findings = []
        check(False, f"mixed naive/aware timestamps raised {error!r} instead of a finding")
    check(
        any("timezone-qualified" in str(f) for f in tz_findings),
        f"a naive timestamp must be REJECTED, not assumed to be UTC: {[str(f) for f in tz_findings]}",
    )

    # Hostile: a foreign base cannot empty the change surface.
    foreign = json.loads(json.dumps(changed))
    other = json.loads(json.dumps(previous))
    other["increment"]["increment_id"] = "some-other-increment"
    blocked(foreign, "different increment_id", "foreign base", other)

    # Hostile: omitting fix_reclosure while supplying a base must not bypass the diff.
    opt_out = json.loads(json.dumps(changed))
    del opt_out["fix_reclosure"]
    opt_out["record_kind"] = "initial"
    blocked(opt_out, "must declare the fix that produced it", "opt-out re-closure", previous)

    # Hostile: an alternate inventory file (with its own matching hash) cannot
    # stand in for the one the record names.
    blocked(
        base,
        "is not the file actually checked",
        "substituted inventory file",
        None,
        ["upload", "remove"],
        "some/other-inventory.txt",
    )

    # Hostile: a backdated clone is not a predecessor.
    clone = json.loads(json.dumps(base))
    clone["record_kind"] = "revision"
    clone["increment"]["increment_id"] = "attachment-upload"
    clone["increment"]["exact_base"] = "1" * 40
    clone["evaluated_at"] = "2026-07-28T03:00:00+00:00"
    clone["fix_reclosure"] = {
        "fix_id": "fix-clone",
        "introduced_at": "2026-07-28T01:00:00+00:00",
        "base_record_ref": "previous",
        "base_record_sha256": "0" * 64,
        "base_exact_base": "0" * 40,
    }
    backdated = json.loads(json.dumps(base))
    backdated["increment"]["increment_id"] = "attachment-upload"
    backdated["evaluated_at"] = "2026-07-27T00:00:00+00:00"
    blocked(clone, "byte-equivalent to its base", "backdated clone as predecessor", backdated)

    # Hostile: a base at a different revision than the one declared.
    wrong_lineage = json.loads(json.dumps(changed))
    other_base = json.loads(json.dumps(previous))
    other_base["increment"]["exact_base"] = "9" * 40
    blocked(wrong_lineage, "not the declared", "base at an undeclared revision", other_base)

    # The shape gate must work without jsonschema installed (clean checkout).
    schema_path = SCHEMA_PATH
    check(validate_shape(base, schema_path) == [], "the shipped sample must satisfy the shape gate")
    nested_bad = json.loads(json.dumps(base))
    nested_bad["operations"][0]["unexpected_nested"] = True
    check(
        any("unexpected field" in str(f) for f in validate_shape(nested_bad, schema_path)),
        "an unknown nested key must be a shape finding, not a traceback",
    )

    # Hostile: trimming record AND inventory together cannot hide an operation
    # that still exists in the code surface.
    joint = json.loads(json.dumps(base))
    joint["operations"] = [op for op in joint["operations"] if op["id"] != "list"]
    joint["concurrency_matrix"] = [
        cell for cell in joint["concurrency_matrix"] if "list" not in cell["pair"]
    ]
    blocked(joint, "exists in the project code surface", "joint record+inventory trim", None, ["upload", "remove"])

    # Hostile: a modelled operation that no handler backs.
    invented_op = json.loads(json.dumps(base))
    invented_op["operations"].append(
        {
            "id": "ghost",
            "kind": "read",
            "source_ref": "nowhere.ts:GET",
            "reads": ["attachment"],
            "writes": [],
        }
    )
    blocked(
        invented_op,
        "does not exist in the project code surface",
        "modelled ghost operation",
        None,
        ["upload", "remove", "list", "ghost"],
    )

    # Hostile: a duplicated identity with a conflicting state machine.
    duplicated = json.loads(json.dumps(base))
    shadow = json.loads(json.dumps(duplicated["identities"][0]))
    shadow["owner"] = "someone else"
    shadow["states"] = ["x", "y"]
    shadow["transitions"] = [{"from": "x", "to": "y", "trigger": "shadow"}]
    duplicated["identities"].append(shadow)
    blocked(duplicated, "duplicate identity", "shadowed identity definition")

    # Hostile: an implicit revision, and a base that is not the file named.
    implicit = json.loads(json.dumps(changed))
    implicit["record_kind"] = "initial"
    blocked(implicit, "an initial record may not declare fix_reclosure", "implicit revision", previous)
    mismatched_ref = json.loads(json.dumps(changed))
    blocked(
        mismatched_ref,
        "is not the file actually diffed",
        "synthetic base under another name",
        previous,
        None,
        inventory_path,
        "some/other-base.json",
    )

    # Round 5: the record cannot choose the discovery scope at all.
    scoped = json.loads(json.dumps(base))
    scoped["inventory_source"]["discovery"] = {
        "globs": ["fixtures/implementation-contract-closure/surface/upload.ts"],
        "pattern": "^// operation: (?P<operation>[a-z]+)$",
    }
    check(
        any("unexpected field" in str(f) for f in validate_shape(scoped, SCHEMA_PATH)),
        "a record may not carry its own discovery scope",
    )

    # Containment: escapes are refused rather than followed, in-process.
    escaped, errors = discover_operations(
        REPO_ROOT, ["../*.ts", "/etc/*.conf"], r"^//\s*operation:\s*(?P<operation>[a-z]+)\s*$"
    )
    check(escaped == set(), "a discovery walk must not read outside the repository")
    check(
        len(errors) == 2 and all("leaves the repository" in e for e in errors),
        f"both escape attempts must be reasoned findings: {errors!r}",
    )
    _, abs_errors = discover_operations(REPO_ROOT, ["/absolute/**/*.ts"], r"(?P<operation>x)")
    check(
        abs_errors and "leaves the repository" in abs_errors[0],
        "an absolute glob must be a finding, never a NotImplementedError",
    )

    # A capture that is not a well-formed id is never echoed back.
    _, capture_errors = discover_operations(
        REPO_ROOT,
        ["fixtures/implementation-contract-closure/surface/*.ts"],
        r"^//\s*operation:\s*(?P<operation>.*)$",
    )
    check(
        all("operation:" not in e or "not a well-formed" in e for e in capture_errors),
        "file content must never be reflected into a finding",
    )

    # Lineage authority: the ledger decides, not the record.
    self_initial = json.loads(json.dumps(changed))
    self_initial["record_kind"] = "initial"
    del self_initial["fix_reclosure"]
    blocked(self_initial, "cannot call itself initial", "changed record posing as initial", previous)

    synthetic = json.loads(json.dumps(changed))
    synthetic["fix_reclosure"]["base_record_sha256"] = "a" * 64
    blocked(synthetic, "must supersede the last accepted record", "synthetic predecessor", previous)

    # Round 6/7: the authority boundary and its provenance.
    check(
        any(
            "no trusted base revision" in str(f)
            for f in validate_record(base, None, inventory, inventory_path, None, REPO_ROOT, None)
        ),
        "without a trusted base revision the authority files cannot be trusted",
    )
    for self_trust in (".", "HEAD"):
        findings = validate_record(
            base, None, inventory, inventory_path, None, REPO_ROOT, self_trust
        )
        check(
            any(
                ("is not a commit" in str(f)) or ("cannot vouch for itself" in str(f))
                for f in findings
            ),
            f"self-trust via {self_trust!r} must be refused: {[str(f) for f in findings]!r}",
        )
    check(
        any(
            "not an ancestor of HEAD" in str(f) or "is not a commit" in str(f)
            for f in validate_record(
                base, None, inventory, inventory_path, None, REPO_ROOT, "0" * 40
            )
        ),
        "a revision that is not this work's ancestor must be refused",
    )

    with tempfile.TemporaryDirectory() as tmp:
        bad_shape = Path(tmp) / "shape"
        (bad_shape / ".fairy").mkdir(parents=True)
        (bad_shape / ".fairy" / "contract-surface.json").write_text("[]", encoding="utf-8")
        config, errors = load_authority(bad_shape, PROJECT_SURFACE_CONFIG, {"globs": list, "pattern": str})
        check(
            config is None and any("must be a JSON object" in e for e in errors),
            "a root-array authority file must be a finding, not silent disablement",
        )
        missing_field = Path(tmp) / "field"
        (missing_field / ".fairy").mkdir(parents=True)
        (missing_field / ".fairy" / "contract-surface.json").write_text(
            json.dumps({"globs": ["a"]}), encoding="utf-8"
        )
        config, errors = load_authority(
            missing_field, PROJECT_SURFACE_CONFIG, {"globs": list, "pattern": str}
        )
        check(config is None and any("missing required field" in e for e in errors), "a missing authority field is RED")

        aliased = Path(tmp) / "alias"
        (aliased / ".FAIRY").mkdir(parents=True)
        (aliased / ".FAIRY" / "contract-surface.json").write_text("{}", encoding="utf-8")
        _, alias_errors = authority_file(aliased, PROJECT_SURFACE_CONFIG)
        check(
            any("no exact entry" in e for e in alias_errors),
            "a case-aliased authority directory must not be accepted as the exact path",
        )

        linked = Path(tmp) / "link"
        (linked / ".fairy").mkdir(parents=True)
        outside = Path(tmp) / "outside.json"
        outside.write_text("{}", encoding="utf-8")
        (linked / ".fairy" / "contract-surface.json").symlink_to(outside)
        _, link_errors = authority_file(linked, PROJECT_SURFACE_CONFIG)
        check(any("symlink" in e for e in link_errors), "a symlinked authority file must be refused")

    # Hostile: a self-declared closure flag must be rejected outright.
    declared = json.loads(json.dumps(base))
    declared["closure_reached"] = True
    blocked(declared, "closure is derived, never declared", "self-declared closure")

    # CLI-boundary controls: a malformed external artifact must be a reasoned
    # RED, never a traceback.
    import subprocess

    here = Path(__file__).resolve()
    repo_root = here.parents[1]
    record_path = repo_root / "examples" / "implementation-contract-closure.json"
    good_inventory = repo_root / "examples" / "implementation-contract-closure.inventory.txt"

    def cli(inventory_file: Path) -> tuple[int, str]:
        result = subprocess.run(
            [sys.executable, str(here), "validate", "--record", str(record_path),
             "--inventory", str(inventory_file)],
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout + result.stderr

    with tempfile.TemporaryDirectory() as tmp:
        broken = repo_root / "examples" / ".contract-closure-selftest-tmp.txt"
        try:
            broken.write_bytes(b"upload\nremove\n\xff\xfe\n")
            code, output = cli(broken)
            check(code == 1 and "not UTF-8" in output, f"invalid UTF-8 inventory must be a reasoned RED: {output!r}")
            broken.write_text("upload\nupload\nremove\nlist\n", encoding="utf-8")
            code, output = cli(broken)
            check(code == 1 and "duplicate operations" in output, "a duplicated inventory id must be RED")
            broken.write_text("# only comments\n", encoding="utf-8")
            code, output = cli(broken)
            check(code == 1 and "empty" in output, "an empty inventory must be RED")
        finally:
            broken.unlink(missing_ok=True)
        outside = Path(tmp) / "inventory.txt"
        outside.write_text("upload\nremove\nlist\n", encoding="utf-8")
        code, output = cli(outside)
        check(code == 1 and "outside the repository" in output, "an out-of-tree inventory must be RED")

    provenance_dir.cleanup()
    if failures:
        for failure in failures:
            print(f"[RED    ] {failure}")
        print(f"implementation contract closure selftest FAILED: {len(failures)} control(s)")
        return 1
    print(f"implementation contract closure selftest OK: {CONTROL_COUNT} controls")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    path = Path(args.record)
    try:
        raw = path.read_text(encoding="utf-8")
        record = json.loads(raw)
    except UnicodeDecodeError as error:
        print(f"[RED    ] record {path} is not UTF-8: {error}")
        return 1
    except (OSError, json.JSONDecodeError) as error:
        print(f"[RED    ] record {path} is not readable JSON: {error}")
        return 1
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "implementation-contract-closure.schema.json"
    shape_findings = validate_shape(record, schema_path)
    if shape_findings:
        for finding in shape_findings:
            print(f"[RED    ] {finding}")
        print(f"implementation contract closure: {len(shape_findings)} shape violation(s)")
        return 1
    inventory = None
    if args.inventory:
        inventory_path = Path(args.inventory)
        # The canonical inventory must be a repo-tracked artifact, so any edit
        # to it lands in the same reviewed diff as the record that cites it.
        # An out-of-tree file would let the inventory be swapped privately.
        repo_root = Path(__file__).resolve().parents[1]
        try:
            resolved = inventory_path.resolve()
            resolved.relative_to(repo_root)
        except (OSError, ValueError):
            print(
                f"[RED    ] canonical inventory {inventory_path} is outside the repository — it must "
                "be a tracked artifact so its content is reviewed with the record"
            )
            return 1
        try:
            inventory_raw = inventory_path.read_bytes()
        except OSError as error:
            print(f"cannot read canonical inventory {inventory_path}: {error}")
            return 2
        try:
            decoded = inventory_raw.decode("utf-8")
        except UnicodeDecodeError as error:
            print(f"[RED    ] canonical inventory is not UTF-8: {error}")
            return 1
        inventory = [
            line.strip()
            for line in decoded.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if not inventory:
            print("[RED    ] canonical inventory is empty — an empty inventory covers nothing")
            return 1
        duplicates = sorted({op for op in inventory if inventory.count(op) > 1})
        if duplicates:
            print(f"[RED    ] canonical inventory has duplicate operations: {duplicates}")
            return 1
        malformed = sorted({op for op in inventory if not re.fullmatch(r"[A-Za-z0-9_.:-]+", op)})
        if malformed:
            print(f"[RED    ] canonical inventory has malformed operation ids: {malformed}")
            return 1
        declared_hash = (record.get("inventory_source") or {}).get("sha256")
        actual_hash = hashlib.sha256(inventory_raw).hexdigest()
        if declared_hash and declared_hash != actual_hash:
            print(
                f"[RED    ] inventory_source.sha256: declared {declared_hash} but the supplied "
                f"inventory hashes to {actual_hash}"
            )
            return 1
    base = None
    if args.base:
        base_path = Path(args.base)
        try:
            base_raw = base_path.read_bytes()
            base = json.loads(base_raw.decode("utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
            print(f"[RED    ] base record {base_path} is not readable JSON/UTF-8: {error}")
            return 1
        if not isinstance(base, dict):
            print("[RED    ] base record is not a JSON object")
            return 1
        for table in ("operations", "identities", "failure_matrix", "concurrency_matrix"):
            value = base.get(table, [])
            if value is not None and not isinstance(value, list):
                print(f"[RED    ] base record {table} is not a list")
                return 1
            if isinstance(value, list) and any(not isinstance(item, dict) for item in value):
                print(f"[RED    ] base record {table} contains a non-object entry")
                return 1
        declared = (record.get("fix_reclosure") or {}).get("base_record_sha256")
        actual = hashlib.sha256(base_raw).hexdigest()
        if declared and declared != actual:
            print(
                f"[RED    ] fix_reclosure.base_record_sha256: declared {declared} but the supplied "
                f"base hashes to {actual}"
            )
            return 1
    findings = validate_record(
        record,
        base,
        inventory,
        args.inventory,
        args.base,
        Path(__file__).resolve().parents[1],
        args.trusted_base,
    )
    if findings:
        for finding in findings:
            print(f"[RED    ] {finding}")
        print(f"implementation contract closure: {len(findings)} unclosed cell(s) — implementation must not start")
        return 1
    print("implementation contract closure: closed (cross product complete, no blank cell)")
    return 0


def command_sample(_: argparse.Namespace) -> int:
    print(json.dumps(sample_record(), ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true", help="run the hostile self-controls")
    subparsers = parser.add_subparsers(dest="command")
    validate = subparsers.add_parser("validate", help="validate a closure record")
    validate.add_argument("--record", required=True)
    validate.add_argument(
        "--base",
        help="the previous version of this record; required whenever fix_reclosure is present",
    )
    validate.add_argument(
        "--trusted-base",
        help="the Git revision the authority files must match (e.g. the merge base); read from the "
        "committed object, so a working tree cannot vouch for itself",
    )
    validate.add_argument(
        "--inventory",
        help="the EXTERNAL canonical operation inventory (one id per line), bound by sha256",
    )
    validate.set_defaults(func=command_validate)
    sample = subparsers.add_parser("sample", help="print a passing sample record")
    sample.set_defaults(func=command_sample)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.selftest:
        return run_selftest()
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
