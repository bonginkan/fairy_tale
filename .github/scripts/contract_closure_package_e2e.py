#!/usr/bin/env python3
"""Gate a DIFFERENT Git project from the extracted release package.

Everything else in CI runs the gate from this checkout against this checkout,
which cannot distinguish "the tool works" from "the tool happens to sit in the
repository it is measuring". This control builds the release tarball, extracts
it somewhere else, creates an unrelated Git project with its own authority,
its own code surface and its own vocabulary, and validates that project through
the extracted copy — then checks the hostile cases where the two roots could be
confused for each other.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Deliberately unlike the fairy_tale fixtures: a different surface directory, a
# different comment syntax and operation ids that appear nowhere in the
# package, so a result can only come from the target project's own config.
SURFACE = {
    "create": "# op: create\ndef create_hold(): ...\n",
    "cancel": "# op: cancel\ndef cancel_hold(): ...\n",
}

AUTHORITY = {
    "purpose": "target project authority",
    "globs": ["service/handlers/*.py"],
    "pattern": r"^#\s*op:\s*(?P<operation>[A-Za-z0-9_.:-]+)\s*$",
    "integration_ref": "origin/trunk",
}

INVENTORY = "# canonical operation inventory\ncreate\ncancel\n"


def record_for(inventory_sha: str, exact_base: str) -> dict:
    def failure(op: str) -> dict:
        return {
            "operation": op,
            "success": f"{op} committed and visible to the peer",
            "failure": "nothing written; the caller sees the rejection",
            "unknown": "commit outcome unknown: the hold document is re-read canonically",
            "peer_observes": "either the committed hold or no hold at all",
            "reclaimer": "hold reaper",
            "residue_discoverable_by": "hold id is derived from the request key",
        }

    return {
        "schema": "fairy.implementation-contract-closure.v1",
        "record_kind": "initial",
        "increment": {
            "repo": "example/holds",
            "exact_base": exact_base,
            "increment_id": "hold-lifecycle",
        },
        "evaluated_at": "2026-07-28T00:00:00+00:00",
        "inventory_source": {
            "kind": "route_manifest",
            "ref": "docs/operations.txt",
            "sha256": inventory_sha,
        },
        "operations": [
            {
                "id": "create",
                "kind": "write",
                "source_ref": "service/handlers/create.py:create_hold",
                "reads": ["hold"],
                "writes": ["hold"],
            },
            {
                "id": "cancel",
                "kind": "write",
                "source_ref": "service/handlers/cancel.py:cancel_hold",
                "reads": ["hold"],
                "writes": ["hold"],
            },
        ],
        "identities": [
            {
                "id": "hold",
                "scope": "persisted",
                "owner": "requesting account",
                "states": ["held", "cancelled"],
                "transitions": [{"from": "held", "to": "cancelled", "trigger": "cancel"}],
                "cleared_by": ["cancel", "hold reaper"],
                "generation_binding": "request key (deterministic document id)",
            }
        ],
        "failure_matrix": [failure("create"), failure("cancel")],
        "concurrency_matrix": [
            {
                "pair": ["create", "create"],
                "disposition": "serialized",
                "serialization_point": {"object": "hold"},
                "loser_outcome": "duplicate rejected by the deterministic id",
                "both_orders_tested": ["races: A then B", "races: B then A"],
            },
            {
                "pair": ["cancel", "create"],
                "disposition": "serialized",
                "serialization_point": {"object": "hold"},
                "loser_outcome": "cancel loses; the hold stays held and is retried",
                "both_orders_tested": ["races: cancel first", "races: create first"],
            },
            {
                "pair": ["cancel", "cancel"],
                "disposition": "serialized",
                "serialization_point": {"object": "hold"},
                "loser_outcome": "second cancel is a no-op on an already cancelled hold",
                "both_orders_tested": ["races: A then B", "races: B then A"],
            },
        ],
        "platform_invariants": [
            {
                "rule": "a transaction may not read after it writes",
                "verified_by": "vendor documentation + a fake that enforces it in tests",
            }
        ],
    }


def build_package(workspace: Path) -> Path:
    out = workspace / "package"
    out.mkdir()
    tarball = out / "fairy-tale-skills.tar.gz"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "package_skills.py"), "--output", str(tarball)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        raise SystemExit(f"[RED    ] package build failed: {result.stdout}{result.stderr}")
    if not tarball.exists():
        raise SystemExit(f"[RED    ] the packager reported success but wrote no tarball: {result.stdout}")
    tarballs = [tarball]
    extracted = workspace / "extracted"
    extracted.mkdir()
    with tarfile.open(tarballs[0]) as archive:
        for member in archive.getmembers():
            target = (extracted / member.name).resolve()
            if not str(target).startswith(str(extracted.resolve())):
                raise SystemExit(f"[RED    ] tarball escapes its directory: {member.name}")
        archive.extractall(extracted)
    matches = sorted(extracted.glob("**/scripts/implementation_contract_closure.py"))
    if len(matches) != 1:
        raise SystemExit(
            "[RED    ] the released package does not carry exactly one contract gate: "
            f"{[str(m) for m in matches]}"
        )
    return matches[0]


ENV = {
    "GIT_AUTHOR_NAME": "e2e",
    "GIT_AUTHOR_EMAIL": "e2e@example.invalid",
    "GIT_COMMITTER_NAME": "e2e",
    "GIT_COMMITTER_EMAIL": "e2e@example.invalid",
    "PATH": os.environ.get("PATH", ""),
}


def make_target(workspace: Path) -> tuple[Path, str]:
    root = workspace / "target"
    (root / "service" / "handlers").mkdir(parents=True)
    (root / ".fairy").mkdir()
    (root / "docs").mkdir()
    for name, body in SURFACE.items():
        (root / "service" / "handlers" / f"{name}.py").write_text(body, encoding="utf-8")
    (root / ".fairy" / "contract-surface.json").write_text(
        json.dumps(AUTHORITY, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (root / ".fairy" / "contract-closure-lineage.json").write_text(
        json.dumps({"purpose": "target lineage", "increments": {}}, indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "docs" / "operations.txt").write_text(INVENTORY, encoding="utf-8")

    def git(*args: str) -> subprocess.CompletedProcess:
        env = dict(ENV)
        env["HOME"] = str(workspace)
        return subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, env=env
        )

    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "authority")
    # The target names its OWN integration branch; the package must follow the
    # target's choice rather than the one its own repository happens to use.
    git("update-ref", "refs/remotes/origin/trunk", "HEAD")
    base = git("rev-parse", "HEAD").stdout.strip()
    (root / "README.md").write_text("work\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "work")
    return root, base


def run(gate: Path, target: Path, record: Path, extra: list[str] | None = None) -> tuple[int, dict]:
    args = [
        sys.executable,
        str(gate),
        "validate",
        "--record",
        str(record),
        "--repo-root",
        str(target),
        "--inventory",
        str(target / "docs" / "operations.txt"),
        "--integration-ref",
        "origin/trunk",
        *(extra or []),
    ]
    result = subprocess.run(args, capture_output=True, text=True, cwd=str(target))
    verdict: dict = {}
    for line in result.stdout.splitlines():
        if line.startswith("VERDICT "):
            verdict = json.loads(line[len("VERDICT ") :])
    if "Traceback" in result.stderr:
        raise SystemExit(f"[RED    ] the gate crashed instead of reporting:\n{result.stderr}")
    return result.returncode, verdict


def main() -> int:
    workspace = Path(tempfile.mkdtemp(prefix="contract-closure-e2e-"))
    controls = 0
    try:
        gate = build_package(workspace)
        controls += 1
        target, base = make_target(workspace)
        inventory_sha = hashlib.sha256(
            (target / "docs" / "operations.txt").read_bytes()
        ).hexdigest()
        record_path = workspace / "record.json"
        record = record_for(inventory_sha, base)
        record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

        code, verdict = run(gate, target, record_path, ["--trusted-base", base])
        if code != 0 or not verdict.get("closed"):
            print(
                "[RED    ] the extracted package could not close a valid record for another "
                f"project: {verdict.get('findings')}"
            )
            return 1
        controls += 1

        def must_fail(label: str, code: int, verdict: dict, expect: str) -> bool:
            nonlocal controls
            controls += 1
            findings = " ".join(verdict.get("findings", []))
            if code == 0 or verdict.get("closed"):
                print(f"[RED    ] hostile case accepted: {label}")
                return False
            if expect not in findings:
                print(
                    f"[RED    ] {label} was rejected for the wrong reason: expected {expect!r} in "
                    f"{findings!r}"
                )
                return False
            return True

        ok = True

        # The target's surface grows an operation the record never mentions.
        # Only the TARGET's globs and pattern can see it.
        (target / "service" / "handlers" / "extend.py").write_text(
            "# op: extend\ndef extend_hold(): ...\n", encoding="utf-8"
        )
        code, verdict = run(gate, target, record_path, ["--trusted-base", base])
        ok &= must_fail("operation present in the target's code but not the record", code, verdict, "extend")
        (target / "service" / "handlers" / "extend.py").unlink()

        # An inventory that lives inside the INSTALLATION rather than the
        # target: containment must be measured against the project under test.
        foreign = gate.resolve().parents[1] / "foreign-inventory.txt"
        foreign.write_text(INVENTORY, encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(gate),
                "validate",
                "--record",
                str(record_path),
                "--repo-root",
                str(target),
                "--inventory",
                str(foreign),
                "--integration-ref",
                "origin/trunk",
                "--trusted-base",
                base,
            ],
            capture_output=True,
            text=True,
        )
        controls += 1
        if result.returncode == 0 or "outside the project being validated" not in result.stdout:
            print(
                "[RED    ] an inventory shipped with the gate was accepted for another project: "
                f"{result.stdout.strip()[:300]}"
            )
            ok = False
        foreign.unlink()

        # The working tree disagrees with the committed authority: the gate
        # must read the target's committed object, not its files on disk.
        authority = target / ".fairy" / "contract-surface.json"
        original = authority.read_bytes()
        widened = dict(AUTHORITY)
        widened["globs"] = ["service/handlers/create.py"]
        authority.write_text(json.dumps(widened, indent=2) + "\n", encoding="utf-8")
        code, verdict = run(gate, target, record_path, ["--trusted-base", base])
        ok &= must_fail("working-tree authority differing from the trusted base", code, verdict, "trusted base")
        authority.write_bytes(original)

        # The caller picks an integration ref the target's authority did not.
        code, verdict = run(
            gate,
            target,
            record_path,
            ["--trusted-base", base, "--integration-ref", "origin/main"],
        )
        # run() passes origin/trunk first; the later flag wins in argparse.
        ok &= must_fail("caller-chosen integration ref", code, verdict, "authority")

        if not ok:
            return 1
        print(f"contract closure package E2E OK: {controls} controls")
        return 0
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
