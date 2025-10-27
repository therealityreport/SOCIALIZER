#!/usr/bin/env python3
"""
SOCIALIZER task time tracker.

This CLI helps the team capture how long each task (and its phase) actually
takes to complete. It parses the master task list for task metadata, records
timing sessions to a persistent log, and can print summaries by phase.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent
MASTER_TASK_LIST = REPO_ROOT / "docs" / "MasterTaskList.md"
TRACKING_FILE = REPO_ROOT / "data" / "processed" / "task_time_tracking.json"


@dataclass
class TaskMetadata:
    task_id: str
    description: str
    phase: str
    section: str
    status: str


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_master_task_list(path: Path) -> Dict[str, TaskMetadata]:
    """
    Parse docs/MasterTaskList.md to map task IDs to their metadata.
    """
    tasks: Dict[str, TaskMetadata] = {}
    if not path.exists():
        return tasks

    current_phase = "Uncategorized"
    current_section = "General"
    task_pattern = re.compile(
        r"- \[(?P<status> |x|X)\]\s+\*\*(?P<task_id>[^*]+)\*\*:\s*(?P<description>.+)"
    )

    with path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if line.startswith("## "):
                header = line[3:].strip()
                if header.lower().startswith("phase"):
                    current_phase = header
            elif line.startswith("### "):
                current_section = line[4:].strip()
            elif line.startswith("- ["):
                match = task_pattern.match(line)
                if match:
                    task_id = match.group("task_id").strip()
                    description = match.group("description").strip()
                    status_flag = match.group("status").lower()
                    status = "complete" if status_flag == "x" else "open"
                    tasks[task_id] = TaskMetadata(
                        task_id=task_id,
                        description=description,
                        phase=current_phase,
                        section=current_section,
                        status=status,
                    )
    return tasks


def ensure_tracking_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        default_payload = {"sessions": [], "active": {}, "metadata": {"created": isoformat(now_utc())}}
        path.write_text(json.dumps(default_payload, indent=2), encoding="utf-8")


def load_tracking_data(path: Path) -> Dict[str, object]:
    ensure_tracking_file(path)
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_tracking_data(path: Path, payload: Dict[str, object]) -> None:
    payload.setdefault("metadata", {})["updated"] = isoformat(now_utc())
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def format_elapsed(seconds: float) -> str:
    seconds = int(round(seconds))
    if seconds <= 0:
        return "0m"
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts: List[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs and (not hours or not minutes):
        parts.append(f"{secs}s")
    return " ".join(parts) or "0m"


def parse_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Unable to parse datetime: {value}") from exc


def lookup_task(tasks: Dict[str, TaskMetadata], task_id: str) -> Optional[TaskMetadata]:
    if task_id in tasks:
        return tasks[task_id]
    for meta in tasks.values():
        if meta.task_id.lower() == task_id.lower():
            return meta
    return None


def normalize_task_id(task_id: str) -> str:
    return task_id.strip().upper()


def handle_start(args: argparse.Namespace, tasks: Dict[str, TaskMetadata], data: Dict[str, object]) -> int:
    task_id_input = args.task_id.strip()
    normalized = normalize_task_id(task_id_input)
    meta = lookup_task(tasks, normalized)

    if meta is None and not args.description:
        print(
            f"Task '{task_id_input}' not found in MasterTaskList.md. "
            "Provide --description (and optionally --phase/--section) to record it anyway.",
            file=sys.stderr,
        )
        return 1

    canonical_id = meta.task_id if meta else normalized
    active: Dict[str, dict] = data.setdefault("active", {})

    for key in list(active.keys()):
        if key.lower() == canonical_id.lower():
            print(f"Task '{canonical_id}' is already being tracked (started at {active[key]['start']}).", file=sys.stderr)
            return 1

    timer_start = now_utc()
    entry = {
        "task_id": canonical_id,
        "phase": (meta.phase if meta else args.phase) or "Uncategorized",
        "section": (meta.section if meta else args.section) or "General",
        "description": (meta.description if meta else args.description),
        "start": isoformat(timer_start),
    }
    if args.note:
        entry["start_note"] = args.note

    active[canonical_id] = entry
    save_tracking_data(TRACKING_FILE, data)

    print(
        f"Started tracking {canonical_id} "
        f"({entry['phase']} • {entry['section']}) "
        f"at {entry['start']}"
    )
    return 0


def handle_stop(args: argparse.Namespace, tasks: Dict[str, TaskMetadata], data: Dict[str, object]) -> int:
    task_id_input = args.task_id.strip()
    normalized = normalize_task_id(task_id_input)
    active: Dict[str, dict] = data.setdefault("active", {})

    active_key: Optional[str] = None
    active_entry: Optional[dict] = None
    for key, value in active.items():
        if key.lower() == normalized.lower():
            active_key = key
            active_entry = value
            break

    if not active_entry or active_key is None:
        print(f"No active timer found for task '{task_id_input}'.", file=sys.stderr)
        return 1

    start_dt = parse_datetime(active_entry["start"])
    end_dt = now_utc()
    elapsed_seconds = max(0, int((end_dt - start_dt).total_seconds()))

    session = dict(active_entry)
    session["end"] = isoformat(end_dt)
    session["duration_seconds"] = elapsed_seconds
    if args.note:
        session["stop_note"] = args.note

    sessions: List[dict] = data.setdefault("sessions", [])
    sessions.append(session)

    del active[active_key]
    save_tracking_data(TRACKING_FILE, data)

    print(
        f"Stopped tracking {session['task_id']} "
        f"after {format_elapsed(elapsed_seconds)} "
        f"(started at {session['start']}, stopped at {session['end']})."
    )
    return 0


def enrich_session(session: dict, tasks: Dict[str, TaskMetadata]) -> dict:
    task_id = session.get("task_id")
    meta = lookup_task(tasks, task_id) if task_id else None
    enriched = dict(session)
    if meta:
        enriched.setdefault("phase", meta.phase)
        enriched.setdefault("section", meta.section)
        enriched.setdefault("description", meta.description)
    enriched.setdefault("phase", "Uncategorized")
    enriched.setdefault("section", "General")
    enriched.setdefault("description", "")
    return enriched


def summarise_sessions(
    sessions: Iterable[dict],
    tasks: Dict[str, TaskMetadata],
    filter_phase: Optional[str],
    filter_task: Optional[str],
) -> Tuple[Dict[str, int], Dict[str, dict], int]:
    phase_totals: Dict[str, int] = defaultdict(int)
    task_totals: Dict[str, dict] = {}
    total_seconds = 0

    for session in sessions:
        enriched = enrich_session(session, tasks)
        task_id = enriched["task_id"]
        phase = enriched["phase"]

        if filter_phase and phase.lower() != filter_phase.lower():
            continue
        if filter_task and task_id.lower() != filter_task.lower():
            continue

        seconds = int(enriched.get("duration_seconds", 0))
        phase_totals[phase] += seconds
        total_seconds += seconds

        item = task_totals.setdefault(
            task_id,
            {
                "task_id": task_id,
                "phase": phase,
                "description": enriched.get("description", ""),
                "seconds": 0,
                "sessions": 0,
            },
        )
        item["seconds"] += seconds
        item["sessions"] += 1

    return phase_totals, task_totals, total_seconds


def handle_summary(args: argparse.Namespace, tasks: Dict[str, TaskMetadata], data: Dict[str, object]) -> int:
    sessions: List[dict] = data.get("sessions", [])
    phase_totals, task_totals, total_seconds = summarise_sessions(
        sessions,
        tasks,
        filter_phase=args.phase,
        filter_task=args.task,
    )

    if args.include_open:
        for meta in tasks.values():
            if args.phase and meta.phase.lower() != args.phase.lower():
                continue
            if args.task and meta.task_id.lower() != args.task.lower():
                continue
            task_totals.setdefault(
                meta.task_id,
                {
                    "task_id": meta.task_id,
                    "phase": meta.phase,
                    "description": meta.description,
                    "seconds": 0,
                    "sessions": 0,
                },
            )
            phase_totals.setdefault(meta.phase, 0)

    lines: List[str] = []
    generated_at = isoformat(now_utc())
    lines.append(f"Task time summary generated {generated_at}")

    if args.phase:
        lines.append(f"Filter — phase: {args.phase}")
    if args.task:
        lines.append(f"Filter — task: {args.task}")
    if args.include_open:
        lines.append("Open tasks included (0m recorded).")

    lines.append("")  # blank line

    if phase_totals:
        lines.append("Phase totals:")
        for phase, seconds in sorted(phase_totals.items()):
            lines.append(f"- {phase}: {format_elapsed(seconds)}")
        lines.append("")

    if task_totals:
        lines.append("Task totals:")
        for task_id in sorted(task_totals.keys()):
            item = task_totals[task_id]
            duration = format_elapsed(item["seconds"])
            sessions_count = item["sessions"]
            suffix = f"{sessions_count} session{'s' if sessions_count != 1 else ''}"
            description = item["description"]
            lines.append(
                f"- {task_id} ({item['phase']}) — {duration} across {suffix}"
            )
            if description:
                lines.append(f"  {description}")
        lines.append("")

    if not sessions and not args.include_open:
        lines.append("No recorded sessions yet.")
        lines.append("")

    lines.append(f"Total recorded time: {format_elapsed(total_seconds)}")

    output_text = "\n".join(lines).strip() + "\n"

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text, encoding="utf-8")
        print(f"Summary written to {output_path}")
    else:
        print(output_text, end="")

    return 0


def handle_active(args: argparse.Namespace, tasks: Dict[str, TaskMetadata], data: Dict[str, object]) -> int:
    active: Dict[str, dict] = data.get("active", {})
    if not active:
        print("No active timers.")
        return 0

    now = now_utc()
    print("Active timers:")
    for task_id in sorted(active.keys()):
        entry = enrich_session(active[task_id], tasks)
        start_dt = parse_datetime(entry["start"])
        elapsed = now - start_dt
        print(
            f"- {task_id} ({entry['phase']} • {entry['section']}) — "
            f"{format_elapsed(elapsed.total_seconds())} elapsed (started {entry['start']})"
        )
        description = entry.get("description")
        if description:
            print(f"  {description}")
        if entry.get("start_note"):
            print(f"  Note: {entry['start_note']}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Track actual time spent on SOCIALIZER tasks and phases."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start", help="Start timing a task.")
    start_parser.add_argument("task_id", help="Task ID from MasterTaskList (e.g., INFRA-001).")
    start_parser.add_argument("--note", "-n", help="Optional note for this timer start.", default="")
    start_parser.add_argument("--description", help="Override description if task ID is not in the master list.")
    start_parser.add_argument("--phase", help="Override phase if not in the master list.")
    start_parser.add_argument("--section", help="Override section if not in the master list.")

    stop_parser = subparsers.add_parser("stop", help="Stop timing a task.")
    stop_parser.add_argument("task_id", help="Task ID used when the timer was started.")
    stop_parser.add_argument("--note", "-n", help="Optional note for when the timer stops.", default="")

    summary_parser = subparsers.add_parser("summary", help="Print a time summary by phase and task.")
    summary_parser.add_argument("--phase", help="Filter summary to a specific phase.")
    summary_parser.add_argument("--task", help="Filter summary to a specific task ID.")
    summary_parser.add_argument("--include-open", action="store_true", help="Include tasks without recorded time.")
    summary_parser.add_argument("--output", "-o", help="Write the summary to a file.")

    subparsers.add_parser("active", help="List timers currently in progress.")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    tasks = parse_master_task_list(MASTER_TASK_LIST)
    data = load_tracking_data(TRACKING_FILE)

    if args.command == "start":
        return handle_start(args, tasks, data)
    if args.command == "stop":
        return handle_stop(args, tasks, data)
    if args.command == "summary":
        return handle_summary(args, tasks, data)
    if args.command == "active":
        return handle_active(args, tasks, data)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
