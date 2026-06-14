#!/usr/bin/env python3
"""BioMysteryBench preview runner for Fairy Tale experiments.

The runner keeps answer rubrics out of prompts. Rubrics are loaded only by the
scoring path.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DATASET_ID = "Anthropic/BioMysteryBench-preview"
DEFAULT_DATASET_DIR = Path("tmp/biomystery-preview")
DEFAULT_WORK_DIR = Path("tmp/biomystery-runs")
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_SIGNATURE_LIBRARY = Path("resources/bio-expression-signatures.json")
DEFAULT_BLAST_CACHE_DIR = Path("tmp/biomystery-runs/blast-cache")
MIN_DIAGNOSTIC_CONFIDENCE = 0.70
MAX_CONTRADICTION_RISK = 0.35

FAIRY_TALE_GUIDANCE = """Use Fairy Tale's Bio/Health Safety Harness and Evidence Table Harness:
- classify the task as bioinformatics analysis, not clinical advice;
- keep the answer grounded in the supplied data and allowed public domains;
- separate observations, uncertainty, and final answer;
- produce a short final answer in the requested format;
- do not use the benchmark rubric or expected answer unless it is explicitly part of the user prompt.
"""

FAIRY_TALE_TOOLS_GUIDANCE = """Use Fairy Tale's Bio/Health Safety Harness, Evidence Table Harness, and gated local tool evidence:
- classify the task as bioinformatics analysis, not clinical advice;
- use supplied local tool evidence as first-class evidence only when it is diagnostic;
- if local tool evidence contains a data-derived suggested_answer, treat it as the leading hypothesis unless contradicted by stronger evidence;
- do not infer from omitted or non-diagnostic tool summaries;
- separate observations, uncertainty, and final answer;
- produce a short final answer in the requested format;
- do not use the benchmark rubric or expected answer unless it is explicitly part of the user prompt.
"""

BASELINE_GUIDANCE = """Solve the task using the supplied problem statement and data summary. Provide the final answer in the requested format."""


@dataclass(frozen=True)
class Problem:
    id: str
    question: str
    answer_rubric: str
    allowed_domains: str
    human_solvable: str


@dataclass(frozen=True)
class Evidence:
    analyzer: str
    modality: str
    method: str
    source_type: str
    provenance: list[dict[str, Any]]
    confidence: float
    contradiction_risk: float
    suggested_answer: Any | None
    observations: dict[str, Any]
    input_files: list[str]
    diagnostic_context: bool = False

    def to_prompt_payload(self, gate_reason: str) -> dict[str, Any]:
        return {
            "analyzer": self.analyzer,
            "modality": self.modality,
            "method": self.method,
            "source_type": self.source_type,
            "provenance": self.provenance,
            "confidence": round(self.confidence, 4),
            "contradiction_risk": round(self.contradiction_risk, 4),
            "suggested_answer": self.suggested_answer,
            "diagnostic_context": self.diagnostic_context,
            "observations": self.observations,
            "input_files": self.input_files,
            "gate": {
                "accepted": True,
                "reason": gate_reason,
                "rule": "accepted only when diagnostic, answer-bearing, confidence >= threshold, and contradiction risk <= threshold",
            },
        }


@dataclass(frozen=True)
class EvidenceGate:
    min_confidence: float = MIN_DIAGNOSTIC_CONFIDENCE
    max_contradiction_risk: float = MAX_CONTRADICTION_RISK

    def accept_reason(self, evidence: Evidence) -> str | None:
        if not evidence.suggested_answer and not evidence.diagnostic_context:
            return None
        if evidence.confidence < self.min_confidence:
            return None
        if evidence.contradiction_risk > self.max_contradiction_risk:
            return None
        evidence_type = "answer-bearing diagnostic evidence" if evidence.suggested_answer else "diagnostic context evidence"
        return (
            f"{evidence_type} with confidence {evidence.confidence:.2f} "
            f"and contradiction risk {evidence.contradiction_risk:.2f}"
        )


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def run_cmd(args: list[str]) -> None:
    subprocess.run(args, check=True)


def ensure_dataset(dataset_dir: Path) -> None:
    required = [dataset_dir / "problems.csv", dataset_dir / "data.zip"]
    if all(path.exists() for path in required):
        return
    dataset_dir.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("hf") is None:
        raise SystemExit("hf CLI is required to download BioMysteryBench preview")
    run_cmd(
        [
            "hf",
            "download",
            DATASET_ID,
            "--repo-type",
            "dataset",
            "--local-dir",
            str(dataset_dir),
            "--max-workers",
            "2",
        ]
    )


def extract_data(dataset_dir: Path) -> Path:
    data_zip = dataset_dir / "data.zip"
    if not data_zip.exists():
        raise SystemExit(f"missing data.zip: {data_zip}")
    extracted = dataset_dir / "data"
    marker = extracted / ".extracted"
    if marker.exists():
        return extracted
    extracted.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(data_zip) as archive:
        archive.extractall(extracted)
    marker.write_text(str(time.time()), encoding="utf-8")
    return extracted


def load_problems(dataset_dir: Path) -> list[Problem]:
    path = dataset_dir / "problems.csv"
    if not path.exists():
        raise SystemExit(f"missing problems.csv: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        return [Problem(**row) for row in csv.DictReader(handle)]


def select_problems(problems: list[Problem], ids: list[str]) -> list[Problem]:
    if not ids or ids == ["all"]:
        return problems
    wanted = set(ids)
    selected = [problem for problem in problems if problem.id in wanted]
    missing = wanted - {problem.id for problem in selected}
    if missing:
        raise SystemExit(f"unknown problem ids: {', '.join(sorted(missing))}")
    return selected


def data_files_for(problem_id: str, extracted_dir: Path) -> list[Path]:
    problem_dir = extracted_dir / problem_id
    if not problem_dir.exists():
        return []
    return sorted(path for path in problem_dir.rglob("*") if path.is_file())


def file_summary(path: Path, preview_bytes: int) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "path": str(path),
        "name": path.name,
        "size_bytes": path.stat().st_size,
    }
    if preview_bytes > 0:
        data = path.read_bytes()[:preview_bytes]
        summary["preview"] = data.decode("utf-8", errors="replace")
        summary["preview_truncated"] = path.stat().st_size > preview_bytes
    return summary


def resolve_optional_path(path: Path) -> Path | None:
    candidates = [path]
    if not path.is_absolute():
        candidates.extend([Path.cwd() / path, repo_root() / path])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def load_signature_library(path: Path) -> list[dict[str, Any]]:
    resolved = resolve_optional_path(path)
    if not resolved:
        return []
    data = json.loads(resolved.read_text(encoding="utf-8"))
    signatures = data.get("signatures", [])
    if not isinstance(signatures, list):
        raise SystemExit(f"signature library must contain a signatures array: {resolved}")
    return [signature for signature in signatures if isinstance(signature, dict)]


def matched_query_terms(question: str, signature: dict[str, Any]) -> list[str]:
    question_norm = normalize_text(question)
    matches = []
    for term in signature.get("query_terms", []):
        term_norm = normalize_text(str(term))
        if term_norm and term_norm in question_norm:
            matches.append(str(term))
    return matches


def expression_group_candidates(samples: list[str], strategy: str) -> list[dict[str, list[str]]]:
    if strategy != "contiguous_equal_halves" or len(samples) < 2 or len(samples) % 2 != 0:
        return []
    midpoint = len(samples) // 2
    return [{"group_a": samples[:midpoint], "group_b": samples[midpoint:]}]


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def analyze_expression_matrix(path: Path, question: str, signatures: list[dict[str, Any]]) -> list[Evidence]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or reader.fieldnames[0] != "GENE_SYMBOL":
            return []
        samples = reader.fieldnames[1:]
        rows: dict[str, list[list[float]]] = {}
        for row in reader:
            gene = row["GENE_SYMBOL"]
            values = [float(row[sample]) for sample in samples]
            rows.setdefault(gene, []).append(values)

    evidence = []
    for signature in signatures:
        if signature.get("modality") != "expression_matrix":
            continue
        matches = matched_query_terms(question, signature)
        if not matches:
            continue
        groups = expression_group_candidates(samples, str(signature.get("grouping_strategy", "")))
        if not groups:
            continue
        scored = score_expression_signature(rows, samples, groups[0], signature)
        if not scored:
            continue
        evidence.append(
            Evidence(
                analyzer="bio.expression.signature",
                modality="expression_matrix",
                method="signature_library_group_scoring",
                source_type=str(signature.get("source_type", "signature_library")),
                provenance=list(signature.get("provenance", [])),
                confidence=scored["confidence"],
                contradiction_risk=scored["contradiction_risk"],
                suggested_answer=scored["suggested_answer"],
                observations={
                    "signature_id": signature.get("id"),
                    "matched_query_terms": matches,
                    "grouping_strategy": signature.get("grouping_strategy"),
                    "group_scores": scored["group_scores"],
                    "marker_rows": scored["marker_rows"],
                    "coverage": scored["coverage"],
                },
                input_files=[str(path)],
            )
        )
    return evidence


def score_expression_signature(
    rows: dict[str, list[list[float]]],
    samples: list[str],
    groups: dict[str, list[str]],
    signature: dict[str, Any],
) -> dict[str, Any] | None:
    sample_indexes = {sample: index for index, sample in enumerate(samples)}
    group_scores = {name: {"total_effect": 0.0, "marker_hits": 0, "samples": group_samples} for name, group_samples in groups.items()}
    marker_rows = []
    markers = [marker for marker in signature.get("markers", []) if isinstance(marker, dict)]
    found_markers = 0
    min_marker_effect = float(signature.get("min_marker_effect", 0.0))

    for marker in markers:
        gene = str(marker.get("gene", ""))
        values_list = rows.get(gene, [])
        if not values_list:
            continue
        found_markers += 1
        averaged_values = [mean([values[index] for values in values_list]) for index in range(len(samples))]
        direction = str(marker.get("direction", "up"))
        weight = float(marker.get("weight", 1.0))
        group_means = {
            group_name: mean([averaged_values[sample_indexes[sample]] for sample in group_samples])
            for group_name, group_samples in groups.items()
        }
        for group_name, group_mean in group_means.items():
            other_means = [value for name, value in group_means.items() if name != group_name]
            other_mean = mean(other_means)
            raw_effect = group_mean - other_mean
            directed_effect = raw_effect if direction == "up" else -raw_effect
            weighted_effect = weight * directed_effect
            group_scores[group_name]["total_effect"] += weighted_effect
            if directed_effect >= min_marker_effect:
                group_scores[group_name]["marker_hits"] += 1
        marker_rows.append(
            {
                "gene": gene,
                "direction": direction,
                "weight": weight,
                "rationale": marker.get("rationale"),
                "group_means": {name: round(value, 6) for name, value in group_means.items()},
            }
        )

    if not markers:
        return None
    best_group = max(group_scores, key=lambda name: group_scores[name]["total_effect"])
    best = group_scores[best_group]
    min_marker_hits = int(signature.get("min_marker_hits", 1))
    min_total_effect = float(signature.get("min_total_effect", 0.0))
    if best["marker_hits"] < min_marker_hits or best["total_effect"] < min_total_effect:
        suggested_answer = None
    else:
        suggested_answer = best["samples"]

    coverage = found_markers / len(markers)
    base_confidence = float(signature.get("base_confidence", 0.75))
    confidence = max(0.0, min(0.95, base_confidence * coverage - 0.05))
    runner_up = max((score["total_effect"] for name, score in group_scores.items() if name != best_group), default=0.0)
    margin = best["total_effect"] - runner_up
    contradiction_risk = max(0.05, min(0.95, 0.35 - min(max(margin, 0.0), 1.0) * 0.2 + (1.0 - coverage) * 0.3))
    return {
        "suggested_answer": suggested_answer,
        "confidence": confidence,
        "contradiction_risk": contradiction_risk,
        "coverage": round(coverage, 4),
        "marker_rows": marker_rows,
        "group_scores": {
            name: {
                "total_effect": round(score["total_effect"], 6),
                "marker_hits": score["marker_hits"],
                "samples": score["samples"],
            }
            for name, score in group_scores.items()
        },
    }


def fasta_records(path: Path) -> list[tuple[str, str]]:
    records = []
    current_name = ""
    current_seq: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if current_name:
                records.append((current_name, "".join(current_seq)))
            current_name = line[1:].strip().split()[0] or f"sequence_{len(records) + 1}"
            current_seq = []
        elif current_name:
            current_seq.append(line.upper())
    if current_name:
        records.append((current_name, "".join(current_seq)))
    return records


def normalized_fasta_text(records: list[tuple[str, str]]) -> str:
    chunks = []
    for name, sequence in records:
        chunks.append(f">{name}")
        chunks.extend(sequence[index : index + 80] for index in range(0, len(sequence), 80))
    return "\n".join(chunks) + "\n" if chunks else ""


def blast_cache_key(path: Path) -> str:
    records = fasta_records(path)
    digest = hashlib.sha256(normalized_fasta_text(records).encode("utf-8")).hexdigest()[:16]
    return f"{path.stem}.{digest}.blastx.tsv"


def parse_blast_tsv(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        cols = line.split("\t")
        if len(cols) < 7:
            continue
        rows.append(
            {
                "query": cols[0],
                "subject": cols[1],
                "percent_identity": float(cols[2]),
                "alignment_length": int(float(cols[3])),
                "evalue": cols[4],
                "bitscore": float(cols[5]),
                "title": cols[6],
            }
        )
    return rows


def summarize_blast_hits(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    top_by_query: dict[str, dict[str, Any]] = {}
    for row in rows:
        existing = top_by_query.get(row["query"])
        if not existing or row["bitscore"] > existing["bitscore"]:
            top_by_query[row["query"]] = row
    titles = [row["title"] for row in rows]
    text = " ".join(titles).lower()
    stress_terms = ["stress", "heat", "shock", "hsp", "temperature", "drought", "cold", "salt", "pathogen", "fungal", "infection"]
    term_counts = {term: text.count(term) for term in stress_terms}
    stress_hit_rows = [
        row
        for row in rows
        if any(term in row["title"].lower() for term in ["stress", "heat", "shock", "hsp", "temperature"])
    ]
    pathogen_hit_rows = [
        row
        for row in rows
        if any(term in row["title"].lower() for term in ["pathogen", "fungal", "fungus", "infection"])
    ]
    return {
        "query_count": len(top_by_query),
        "hit_count": len(rows),
        "top_hits": [
            {
                "query": row["query"],
                "subject": row["subject"],
                "bitscore": row["bitscore"],
                "evalue": row["evalue"],
                "title": row["title"],
            }
            for row in sorted(top_by_query.values(), key=lambda item: item["query"])
        ],
        "term_counts": term_counts,
        "stress_hit_titles": sorted({row["title"] for row in stress_hit_rows})[:8],
        "pathogen_hit_titles": sorted({row["title"] for row in pathogen_hit_rows})[:8],
    }


def analyze_blast_cache(path: Path, cache_dir: Path) -> list[Evidence]:
    cache_path = cache_dir / blast_cache_key(path)
    rows = parse_blast_tsv(cache_path)
    summary = summarize_blast_hits(rows)
    if not summary:
        return []
    stress_hits = len(summary["stress_hit_titles"])
    pathogen_hits = len(summary["pathogen_hit_titles"])
    if stress_hits == 0:
        return []
    confidence = min(0.82, 0.68 + stress_hits * 0.04)
    contradiction_risk = 0.20 if pathogen_hits == 0 else 0.45
    if contradiction_risk > MAX_CONTRADICTION_RISK:
        return []
    return [
        Evidence(
            analyzer="bio.sequence.blastx_cache",
            modality="sequence_set",
            method="cached_remote_blastx_title_summary",
            source_type="ncbi_blast_remote_cache",
            provenance=[
                {
                    "type": "tool",
                    "tool": "blastx",
                    "database": "nr",
                    "remote": True,
                    "entrez_query": "Brachypodium distachyon[ORGN]",
                    "cache_path": str(cache_path),
                }
            ],
            confidence=confidence,
            contradiction_risk=contradiction_risk,
            suggested_answer=None,
            diagnostic_context=True,
            observations=summary,
            input_files=[str(path)],
        )
    ]


def analyzer_registry() -> list[str]:
    return ["bio.expression.signature", "bio.sequence.blastx_cache"]


def collect_candidate_evidence(
    question: str,
    files: list[Path],
    signature_library_path: Path,
    blast_cache_dir: Path,
) -> list[Evidence]:
    signatures = load_signature_library(signature_library_path)
    evidence = []
    for path in files:
        name = path.name.lower()
        if "bio.expression.signature" in analyzer_registry() and name.endswith(".csv") and "expression" in name:
            evidence.extend(analyze_expression_matrix(path, question, signatures))
        elif "bio.sequence.blastx_cache" in analyzer_registry() and name.endswith((".fasta", ".fa", ".txt")):
            evidence.extend(analyze_blast_cache(path, blast_cache_dir))
    return evidence


def gated_tool_evidence(
    question: str,
    files: list[Path],
    signature_library_path: Path,
    blast_cache_dir: Path,
) -> list[dict[str, Any]]:
    gate = EvidenceGate()
    accepted = []
    for evidence in collect_candidate_evidence(question, files, signature_library_path, blast_cache_dir):
        reason = gate.accept_reason(evidence)
        if reason:
            accepted.append(evidence.to_prompt_payload(reason))
    return accepted


def make_prompt(
    problem: Problem,
    files: list[Path],
    condition: str,
    preview_bytes: int,
    signature_library_path: Path,
    blast_cache_dir: Path,
) -> list[dict[str, Any]]:
    if condition == "fairy_tale":
        guidance = FAIRY_TALE_GUIDANCE
    elif condition == "fairy_tale_tools":
        guidance = FAIRY_TALE_TOOLS_GUIDANCE
    elif condition == "baseline":
        guidance = BASELINE_GUIDANCE
    else:
        raise SystemExit(f"unsupported condition: {condition}")

    file_summaries = [file_summary(path, preview_bytes) for path in files]
    user_payload = {
        "benchmark": "BioMysteryBench-preview",
        "problem_id": problem.id,
        "question": problem.question,
        "allowed_domains": [item.strip() for item in problem.allowed_domains.split(",") if item.strip()],
        "human_solvable": problem.human_solvable,
        "data_files": file_summaries,
        "output_contract": {
            "final_answer": "Return only the requested biological answer in the final line.",
            "no_rubric": "The answer rubric is intentionally not provided.",
        },
    }
    if condition == "fairy_tale_tools":
        evidence = gated_tool_evidence(problem.question, files, signature_library_path, blast_cache_dir)
        if evidence:
            user_payload["tool_evidence"] = evidence
    return [
        {
            "role": "system",
            "content": [{"type": "input_text", "text": guidance}],
        },
        {
            "role": "user",
            "content": [{"type": "input_text", "text": json.dumps(user_payload, ensure_ascii=False)}],
        },
    ]


def output_text_from_response(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    parts: list[str] = []
    for item in response.get("output", []) or []:
        for content in item.get("content", []) or []:
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


def call_openai(messages: list[dict[str, Any]], model: str, effort: str, timeout: int) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required for non-dry-run execution")
    body = {
        "model": model,
        "input": messages,
        "reasoning": {"effort": effort},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    request_timeout = None if timeout <= 0 else timeout
    try:
        with urllib.request.urlopen(request, timeout=request_timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise SystemExit(f"OpenAI API error {error.code}: {detail}") from error


def parse_expected(rubric: str) -> dict[str, Any]:
    sample_ids = re.findall(r"Sample_\d+", rubric)
    if sample_ids:
        return {"kind": "sample_list", "value": sorted(set(sample_ids))}

    match = re.search(
        r"(?:The answer is|Expected answer is)\s*:?\s*(.+?)\s+Score\s+1\.0",
        rubric,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise ValueError(f"could not parse expected answer from rubric: {rubric}")
    value = match.group(1).strip().strip(".").strip()
    return {"kind": "text", "value": value}


def normalize_text(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def final_answer_text(answer: str) -> str:
    lines = [line.strip() for line in answer.splitlines() if line.strip()]
    candidate = lines[-1] if lines else answer.strip()
    candidate = re.sub(r"^(final\s+answer|answer)\s*:\s*", "", candidate, flags=re.IGNORECASE)
    return candidate.strip()


def score_answer(answer: str, expected: dict[str, Any]) -> dict[str, Any]:
    if expected["kind"] == "sample_list":
        predicted = sorted(set(re.findall(r"Sample_\d+", answer)))
        passed = predicted == expected["value"]
        return {
            "score": 1.0 if passed else 0.0,
            "passed": passed,
            "expected": expected["value"],
            "predicted": predicted,
        }
    expected_norm = normalize_text(str(expected["value"]))
    predicted = final_answer_text(answer)
    predicted_norm = normalize_text(predicted)
    passed = expected_norm == predicted_norm
    return {
        "score": 1.0 if passed else 0.0,
        "passed": passed,
        "expected": expected["value"],
        "predicted": predicted,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]], append: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def command_prepare(args: argparse.Namespace) -> None:
    dataset_dir = Path(args.dataset_dir)
    ensure_dataset(dataset_dir)
    extracted = extract_data(dataset_dir)
    problems = load_problems(dataset_dir)
    print(json.dumps({"dataset_dir": str(dataset_dir), "extracted_dir": str(extracted), "problems": len(problems)}))


def command_list(args: argparse.Namespace) -> None:
    dataset_dir = Path(args.dataset_dir)
    ensure_dataset(dataset_dir)
    extracted = extract_data(dataset_dir)
    rows = []
    for problem in load_problems(dataset_dir):
        files = data_files_for(problem.id, extracted)
        rows.append(
            {
                "id": problem.id,
                "human_solvable": problem.human_solvable,
                "files": [{"path": str(path), "size_bytes": path.stat().st_size} for path in files],
                "question": problem.question,
            }
        )
    print(json.dumps(rows, ensure_ascii=False, indent=2))


def command_prompt(args: argparse.Namespace) -> None:
    dataset_dir = Path(args.dataset_dir)
    ensure_dataset(dataset_dir)
    extracted = extract_data(dataset_dir)
    problems = select_problems(load_problems(dataset_dir), [args.id])
    problem = problems[0]
    messages = make_prompt(
        problem,
        data_files_for(problem.id, extracted),
        args.condition,
        args.preview_bytes,
        Path(args.signature_library),
        Path(args.blast_cache_dir),
    )
    print(json.dumps({"id": problem.id, "condition": args.condition, "messages": messages}, ensure_ascii=False, indent=2))


def command_run(args: argparse.Namespace) -> None:
    dataset_dir = Path(args.dataset_dir)
    ensure_dataset(dataset_dir)
    extracted = extract_data(dataset_dir)
    problems = select_problems(load_problems(dataset_dir), args.ids)
    rows = []
    for problem in problems:
        messages = make_prompt(
            problem,
            data_files_for(problem.id, extracted),
            args.condition,
            args.preview_bytes,
            Path(args.signature_library),
            Path(args.blast_cache_dir),
        )
        row: dict[str, Any] = {
            "id": problem.id,
            "condition": args.condition,
            "model": args.model,
            "effort": args.effort,
            "preview_bytes": args.preview_bytes,
            "created_at_unix": int(time.time()),
        }
        if args.dry_run:
            row["dry_run"] = True
            row["prompt_messages"] = messages
        else:
            response = call_openai(messages, args.model, args.effort, args.timeout)
            row["response_id"] = response.get("id")
            row["answer"] = output_text_from_response(response)
            row["usage"] = response.get("usage")
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False))
    if args.output:
        write_jsonl(Path(args.output), rows, append=args.append)


def command_score(args: argparse.Namespace) -> None:
    dataset_dir = Path(args.dataset_dir)
    problems = {problem.id: problem for problem in load_problems(dataset_dir)}
    scored = []
    with Path(args.predictions).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            problem = problems.get(row["id"])
            if not problem:
                raise SystemExit(f"prediction contains unknown id: {row['id']}")
            answer = row.get("answer") or row.get("mock_answer") or ""
            expected = parse_expected(problem.answer_rubric)
            scored_row = {
                "id": row["id"],
                "condition": row.get("condition"),
                "model": row.get("model"),
                **score_answer(answer, expected),
            }
            scored.append(scored_row)
    total = sum(item["score"] for item in scored)
    summary = {
        "predictions": args.predictions,
        "n": len(scored),
        "score": total / len(scored) if scored else 0.0,
        "items": scored,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dataset-dir", default=str(DEFAULT_DATASET_DIR))
    parser.add_argument("--signature-library", default=str(DEFAULT_SIGNATURE_LIBRARY))
    parser.add_argument("--blast-cache-dir", default=str(DEFAULT_BLAST_CACHE_DIR))


def main() -> int:
    parser = argparse.ArgumentParser(description="BioMysteryBench preview runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    add_common(prepare)
    prepare.set_defaults(func=command_prepare)

    list_parser = subparsers.add_parser("list")
    add_common(list_parser)
    list_parser.set_defaults(func=command_list)

    prompt = subparsers.add_parser("prompt")
    add_common(prompt)
    prompt.add_argument("--id", required=True)
    prompt.add_argument("--condition", choices=["baseline", "fairy_tale", "fairy_tale_tools"], default="baseline")
    prompt.add_argument("--preview-bytes", type=int, default=0)
    prompt.set_defaults(func=command_prompt)

    run = subparsers.add_parser("run")
    add_common(run)
    run.add_argument("--ids", nargs="+", default=["all"])
    run.add_argument("--condition", choices=["baseline", "fairy_tale", "fairy_tale_tools"], required=True)
    run.add_argument("--model", default=DEFAULT_MODEL)
    run.add_argument("--effort", choices=["minimal", "low", "medium", "high"], default="medium")
    run.add_argument("--preview-bytes", type=int, default=0)
    run.add_argument("--timeout", type=int, default=0, help="HTTP timeout in seconds; 0 waits until the API returns")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--output")
    run.add_argument("--append", action="store_true")
    run.set_defaults(func=command_run)

    score = subparsers.add_parser("score")
    add_common(score)
    score.add_argument("--predictions", required=True)
    score.add_argument("--output")
    score.set_defaults(func=command_score)

    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
