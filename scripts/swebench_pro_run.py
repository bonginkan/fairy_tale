#!/usr/bin/env python3
"""Run SWE-Bench Pro patch gathering and evaluation with provenance records."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_HARNESS_DIR = Path("tmp/swe-bench-pro-os")
DEFAULT_VENV_PYTHON = Path("tmp/swe-bench-pro-venv/bin/python")
DEFAULT_RUN_DIR = Path("tmp/swe-bench-pro-runs")


def absolute_path(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


def repo_commit(path: Path) -> str | None:
    if not (path / ".git").exists():
        return None
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def raw_eval_csv_path(manifest: dict[str, Any]) -> Path:
    if manifest.get("raw_eval_csv_path"):
        return Path(manifest["raw_eval_csv_path"]).resolve()
    raw_eval = manifest.get("raw_eval_path")
    if raw_eval:
        return Path(raw_eval).with_suffix(".csv").resolve()
    raise SystemExit("prepared manifest does not contain raw_eval_csv_path or raw_eval_path")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def command_result(command: list[str], cwd: Path, dry_run: bool) -> int:
    printable = " ".join(command)
    if dry_run:
        print(printable)
        return 0
    return subprocess.run(command, cwd=cwd, check=False).returncode


def gather(args: argparse.Namespace) -> int:
    harness_dir = args.harness_dir
    output = (args.output or (args.run_dir / "patches.json")).resolve()
    command = [
        str(args.python),
        "helper_code/gather_patches.py",
        "--directory",
        str(args.pred_dir.resolve()),
        "--prefix",
        args.prefix,
        "--output",
        str(output),
    ]
    record = {
        "benchmark": "SWE-Bench Pro",
        "action": "gather_patches",
        "harness_dir": str(harness_dir),
        "harness_commit": repo_commit(harness_dir),
        "pred_dir": str(args.pred_dir),
        "patch_output": str(output),
        "prefix": args.prefix,
        "command": command,
    }
    write_json(args.run_dir / "gather-manifest.json", record)
    return command_result(command, harness_dir, args.dry_run)


def eval_patches(args: argparse.Namespace) -> int:
    prepared_manifest = load_manifest(args.prepared_manifest)
    raw_csv = raw_eval_csv_path(prepared_manifest)
    harness_dir = args.harness_dir
    output_dir = (args.output_dir or (args.run_dir / "eval")).resolve()
    command = [
        str(args.python),
        "swe_bench_pro_eval.py",
        f"--raw_sample_path={raw_csv}",
        f"--patch_path={args.patch_path.resolve()}",
        f"--output_dir={output_dir}",
        f"--scripts_dir={args.scripts_dir}",
        f"--num_workers={args.num_workers}",
        f"--dockerhub_username={args.dockerhub_username}",
    ]
    if args.use_local_docker:
        command.append("--use_local_docker")
    if args.block_network:
        command.append("--block_network")
    if args.redo:
        command.append("--redo")
    if args.docker_platform:
        command.append(f"--docker_platform={args.docker_platform}")

    record = {
        "benchmark": "SWE-Bench Pro",
        "action": "evaluate_patches",
        "harness_dir": str(harness_dir),
        "harness_commit": repo_commit(harness_dir),
        "prepared_manifest": str(args.prepared_manifest),
        "instance_ids": prepared_manifest.get("instance_ids", []),
        "raw_eval_csv_path": str(raw_csv),
        "patch_path": str(args.patch_path),
        "output_dir": str(output_dir),
        "num_workers": args.num_workers,
        "use_local_docker": args.use_local_docker,
        "block_network": args.block_network,
        "command": command,
        "notes": "Use the same prepared manifest, model, effort, scorer, retry policy, and tool budget for comparable rows.",
    }
    write_json(args.run_dir / "eval-manifest.json", record)
    return command_result(command, harness_dir, args.dry_run)


def plan(args: argparse.Namespace) -> int:
    prepared_manifest = load_manifest(args.prepared_manifest)
    payload = {
        "benchmark": "SWE-Bench Pro",
        "action": "plan",
        "harness_dir": str(args.harness_dir),
        "harness_commit": repo_commit(args.harness_dir),
        "prepared_manifest": str(args.prepared_manifest),
        "instance_ids": prepared_manifest.get("instance_ids", []),
        "agent_tasks_path": prepared_manifest.get("agent_tasks_path"),
        "raw_eval_csv_path": str(raw_eval_csv_path(prepared_manifest)),
        "expected_flow": [
            "Generate one .pred patch file per instance under a prediction directory.",
            "Run this script's gather subcommand to create patches.json.",
            "Run this script's eval subcommand with the same prepared manifest and patches.json.",
            "Report known Fable/Mythos, known or measured GPT-5.5, and measured GPT-5.5 + Fairy Tale in separate cells.",
        ],
    }
    output = args.output or (args.run_dir / "plan-manifest.json")
    write_json(output, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def require_path(path: Path, label: str) -> None:
    if not path.exists():
        raise SystemExit(f"{label} not found: {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SWE-Bench Pro runner wrapper")
    parser.add_argument("--harness-dir", type=Path, default=DEFAULT_HARNESS_DIR)
    parser.add_argument("--python", type=Path, default=DEFAULT_VENV_PYTHON)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR / "current")
    parser.add_argument("--dry-run", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_dry_run_flag(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS)

    plan_parser = subparsers.add_parser("plan")
    add_dry_run_flag(plan_parser)
    plan_parser.add_argument("--prepared-manifest", type=Path, required=True)
    plan_parser.add_argument("--output", type=Path)
    plan_parser.set_defaults(func=plan)

    gather_parser = subparsers.add_parser("gather")
    add_dry_run_flag(gather_parser)
    gather_parser.add_argument("--pred-dir", type=Path, required=True)
    gather_parser.add_argument("--prefix", required=True)
    gather_parser.add_argument("--output", type=Path)
    gather_parser.set_defaults(func=gather)

    eval_parser = subparsers.add_parser("eval")
    add_dry_run_flag(eval_parser)
    eval_parser.add_argument("--prepared-manifest", type=Path, required=True)
    eval_parser.add_argument("--patch-path", type=Path, required=True)
    eval_parser.add_argument("--output-dir", type=Path)
    eval_parser.add_argument("--scripts-dir", default="run_scripts")
    eval_parser.add_argument("--num-workers", type=int, default=4)
    eval_parser.add_argument("--dockerhub-username", default="jefzda")
    eval_parser.add_argument("--use-local-docker", action="store_true")
    eval_parser.add_argument("--block-network", action="store_true", default=True)
    eval_parser.add_argument("--allow-network", action="store_false", dest="block_network")
    eval_parser.add_argument("--redo", action="store_true")
    eval_parser.add_argument("--docker-platform")
    eval_parser.set_defaults(func=eval_patches)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.harness_dir = absolute_path(args.harness_dir)
    args.python = absolute_path(args.python)
    args.run_dir = absolute_path(args.run_dir)
    if hasattr(args, "prepared_manifest"):
        args.prepared_manifest = args.prepared_manifest.resolve()
    require_path(args.harness_dir, "SWE-Bench Pro harness")
    require_path(args.python, "SWE-Bench Pro python")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
