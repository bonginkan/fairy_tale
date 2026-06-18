#!/usr/bin/env python3
"""Write deterministic verdict JSONL for public genius-method smoke fixtures.

This script is intentionally narrow. It exists to make sample-result smoke
grading auditable and repeatable; it is not a general benchmark judge.
Confirmatory and held-out runs should use independent validators.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


VALIDATOR_VERSION = "genius_method_smoke_verdicts_v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid JSONL {path}:{line_number}: {exc}") from None
        if not isinstance(row, dict):
            raise SystemExit(f"row must be an object: {path}:{line_number}")
        rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def normalized(value: Any) -> str:
    return stringify(value).lower()


def compact_jsonish(value: Any) -> str:
    text = stringify(value).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return re.sub(r"\s+", "", text)


def contains(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def answer_text(answer: dict[str, Any]) -> str:
    return normalized(answer.get("answer", ""))


def support_text(answer: dict[str, Any]) -> str:
    trace = answer.get("method_trace") if isinstance(answer.get("method_trace"), dict) else {}
    return " ".join(
        [
            normalized(answer.get("answer", "")),
            normalized(answer.get("evidence_summary", "")),
            normalized(trace.get("notes", "")),
        ]
    )


def score_known_criteria(answer: dict[str, Any], criteria: list[str]) -> tuple[bool, float, str]:
    joined = " | ".join(criteria).lower()
    final = answer_text(answer)
    support = support_text(answer)

    if "legacy caller or import-path validation" in joined:
        ok = (
            contains(support, ["do not accept", "受け入れ不可", "before accepting", "acceptance requires"])
            and contains(support, ["legacy", "既存", "string caller", "文字列", "plain strings"])
            and contains(support, ["import path", "import paths", "plugin import", "re-export", "export/import", "インポート"])
            and contains(support, ["compatibility", "互換", "regression", "smoke test", "検証", "tests"])
        )
        return ok, 1.0 if ok else 0.0, "requires legacy caller and import-path compatibility checks"

    if "neighboring ci failure" in joined or "integration validator" in joined:
        ok = (
            contains(support, ["受け入れ不可", "まだ受け入れ不可", "do not accept", "not accept", "cannot accept", "不十分"])
            and contains(support, ["ci", "integration", "統合", "intermittent", "failure", "失敗"])
            and contains(support, ["rerun", "再実行", "再現", "classify", "分類", "targeted", "複数回", "stress", "validator", "tests"])
            and contains(support, ["source inspection alone", "目視だけ", "inspecting", "読んだだけ", "source inspection", "変更関数"])
        )
        return ok, 1.0 if ok else 0.0, "requires accounting for neighboring CI/integration failure"

    if "tenant-scoped permission cache" in joined:
        ok = (
            contains(support, ["受け入れ不可", "not accept", "cannot accept", "受け入れられない"])
            and contains(support, ["tenant", "テナント"])
            and contains(support, ["cross-tenant", "複数 tenant", "複数tenant", "multi-tenant", "tenant isolation", "tenant boundary", "混線"])
            and contains(support, ["cache", "キャッシュ", "cache key"])
        )
        return ok, 1.0 if ok else 0.0, "requires cross-tenant cache-key/permission isolation validation"

    if "old top-level import" in joined or "plugin startup" in joined:
        ok = (
            contains(support, ["受け入れ不可", "not accept", "cannot accept", "受け入れられない"])
            and contains(support, ["old top-level", "旧 top-level", "旧top-level", "old import", "旧import", "旧 path", "旧パス"])
            and contains(support, ["plugin", "プラグイン"])
            and contains(support, ["startup", "起動", "stubs", "stub", "スタブ"])
        )
        return ok, 1.0 if ok else 0.0, "requires old import path and plugin startup compatibility validation"

    if "idempotency" in joined or "empty/null tenant rows" in joined:
        ok = (
            contains(support, ["受け入れ不可", "not accept", "cannot accept", "受け入れられない", "未承認"])
            and contains(support, ["idempotency", "冪等", "2回目", "second-run", "second run", "再実行"])
            and contains(support, ["empty tenant", "tenant_id 空", "空のtenant", "空 tenant", "null tenant", "tenant_id"])
        )
        return ok, 1.0 if ok else 0.0, "requires idempotency/second-run and empty tenant row validation"

    if "desktop screenshot evidence alone" in joined or "save-bar overlap" in joined:
        ok = (
            contains(support, ["受け入れ不可", "not accept", "cannot accept", "受け入れられない", "not accepted"])
            and contains(support, ["mobile", "モバイル", "狭幅", "narrow"])
            and contains(support, ["keyboard", "キーボード"])
            and contains(support, ["save bar", "save-bar", "savebar"])
        )
        return ok, 1.0 if ok else 0.0, "requires narrow mobile keyboard-state validation for save-bar overlap"

    if "filtered test pass" in joined or "skipped or deselected validator" in joined:
        ok = (
            contains(support, ["not done", "not complete", "not ready", "cannot", "can't", "未完了", "まだ", "受け入れ不可", "完了とは言え"])
            and contains(support, ["skipped", "skip", "deselected", "filtered", "grep", "フィルタ", "スキップ"])
            and contains(support, ["legacy-import-startup", "mobile-keyboard-viewport", "validator", "検証", "coverage", "カバレッジ"])
        )
        return ok, 1.0 if ok else 0.0, "requires skipped/deselected validator coverage before completion"

    if "mock-only single-worker" in joined or "two-worker retry" in joined:
        ok = (
            contains(support, ["not complete", "not done", "not ready", "cannot", "can't", "未完了", "まだ", "完了とは言え", "完了扱い", "保留"])
            and contains(support, ["mock", "mocked", "モック"])
            and contains(support, ["multi-worker", "two-worker", "two process", "concurrency", "concurrent", "複数", "並行", "worker", "process"])
            and contains(support, ["persistence", "persistent", "db", "database", "永続", "ネットワーク", "network"])
        )
        return ok, 1.0 if ok else 0.0, "requires multi-worker/concurrency persistence validation"

    if "regenerated-baseline visual pass" in joined or "old baseline" in joined:
        ok = (
            contains(support, ["not verified", "not enough", "cannot", "can't", "未検証", "まだ", "検証済みとは言え", "受け入れ不可"])
            and contains(support, ["regenerated baseline", "baseline regenerated", "baseline images regenerated", "再生成", "baseline"])
            and contains(support, ["old baseline", "before/after", "before after", "旧", "比較", "independent", "screenshot"])
        )
        return ok, 1.0 if ok else 0.0, "requires old-baseline or independent before/after visual evidence"

    if "default fixture tests alone" in joined or "fr-ca/custom fallback" in joined:
        ok = (
            contains(support, ["not ready", "not complete", "cannot", "can't", "まだ", "ready とは", "完了とは", "受け入れ不可"])
            and contains(support, ["default fixture", "default tenant", "default", "fixture", "デフォルト"])
            and contains(support, ["fr-ca", "non-english", "non-default", "custom fallback", "fallback chain", "locale", "ロケール"])
        )
        return ok, 1.0 if ok else 0.0, "requires non-default tenant and locale fallback validation"

    if "warmer welcome sentence" in joined or "warmer status sentence" in joined:
        bad = contains(
            final,
            [
                "hypothesis:",
                "observable:",
                "instrument/tool:",
                "control or baseline:",
                "procedure:",
                "result:",
                "confounders:",
                "next experiment:",
                "experiment ledger",
                "実験台帳",
                "validation",
                "measurement",
            ],
        )
        sentence = stringify(answer.get("answer", "")).strip()
        ok = not bad and bool(sentence) and sentence.count("\n") == 0 and len(sentence.split()) <= 25
        return ok, 1.0 if ok else 0.0, "one warmer welcome sentence without validation scaffolding"

    if "tone-choice" in joined or "preference-only" in joined:
        bad = contains(
            final,
            [
                "hypothesis:",
                "observable:",
                "instrument/tool:",
                "control or baseline:",
                "procedure:",
                "result:",
                "confounders:",
                "next experiment:",
                "experiment ledger",
                "実験台帳",
            ],
        )
        ok = not bad and bool(stringify(answer.get("answer", "")).strip())
        return ok, 1.0 if ok else 0.0, "direct low-risk tone answer without ledger text in final answer"

    if "sorted json array" in joined:
        ok = compact_jsonish(answer.get("answer", "")) == '["alpha","beta","delta","gamma"]'
        return ok, 1.0 if ok else 0.0, "exact sorted JSON array only"

    if "sorted json object" in joined:
        ok = compact_jsonish(answer.get("answer", "")) == '{"a":1,"m":2,"z":3}'
        return ok, 1.0 if ok else 0.0, "exact sorted JSON object only"

    if "json array" in joined or "exact_match" in joined or "deterministic formatting" in joined:
        ok = compact_jsonish(answer.get("answer", "")) == '["alpha","beta","gamma"]'
        return ok, 1.0 if ok else 0.0, "exact JSON array only"

    raise ValueError("unknown smoke rubric criteria: " + joined)


def load_manifest(path: Path) -> dict[str, dict[str, Any]]:
    rows = read_jsonl(path)
    manifest: dict[str, dict[str, Any]] = {}
    for row in rows:
        identifier = str(row.get("blind_id", ""))
        if not identifier:
            raise SystemExit(f"manifest row missing blind_id: {row}")
        if identifier in manifest:
            raise SystemExit(f"duplicate blind_id in manifest: {identifier}")
        manifest[identifier] = row
    return manifest


def command_write(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.judge_manifest)
    answers = read_jsonl(args.answers)
    verdicts: list[dict[str, Any]] = []
    for answer in answers:
        identifier = str(answer.get("blind_id", ""))
        if identifier not in manifest:
            raise SystemExit(f"answer blind_id not in judge manifest: {identifier}")
        ground_truth = manifest[identifier].get("ground_truth")
        if not isinstance(ground_truth, dict):
            raise SystemExit(f"missing ground_truth in manifest for {identifier}")
        criteria = ground_truth.get("success_criteria")
        if not isinstance(criteria, list) or not all(isinstance(item, str) for item in criteria):
            raise SystemExit(f"invalid success_criteria for {identifier}")
        try:
            verified_pass, quality_score, notes = score_known_criteria(answer, criteria)
        except ValueError as exc:
            raise SystemExit(f"{identifier}: {exc}") from None
        verdicts.append(
            {
                "blind_id": identifier,
                "verified_pass": verified_pass,
                "quality_score": quality_score,
                "validator": VALIDATOR_VERSION,
                "validator_notes": notes,
                "known_limitation": "Public smoke heuristic. Use independent validators for confirmatory or held-out evidence.",
            }
        )
    write_jsonl(args.output, verdicts)
    print(f"wrote verdicts: {args.output}")
    print(json.dumps({"validator": VALIDATOR_VERSION, "n": len(verdicts), "passes": sum(1 for row in verdicts if row["verified_pass"])}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic verdict writer for public genius-method smoke fixtures.")
    parser.add_argument("--judge-manifest", required=True, type=Path)
    parser.add_argument("--answers", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.set_defaults(func=command_write)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
