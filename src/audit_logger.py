import json
from datetime import datetime, timezone
from pathlib import Path


LOG_PATH = Path(__file__).with_name("audit_log.jsonl")


def _timestamp():
    return datetime.now(timezone.utc).isoformat()


def _read_all_entries():
    try:
        with LOG_PATH.open("r") as file:
            return [json.loads(line) for line in file if line.strip()]
    except FileNotFoundError:
        return []


def _write_all_entries(entries):
    with LOG_PATH.open("w") as file:
        for entry in entries:
            file.write(json.dumps(entry) + "\n")


def log_event(entry):
    entry["timestamp"] = _timestamp()

    with LOG_PATH.open("a") as file:
        file.write(json.dumps(entry) + "\n")


def read_log(limit=20):
    entries = _read_all_entries()

    return entries[-limit:]


def mark_classification_under_review(content_id, creator_id, reasoning):
    entries = _read_all_entries()
    updated_entry = None

    for entry in entries:
        if (
            entry.get("content_id") == content_id
            and entry.get("creator_id") == creator_id
            and entry.get("status") == "classified"
        ):
            entry["status"] = "under_review"
            entry["appeal_filed"] = True
            entry["creator_reasoning"] = reasoning
            entry["appeal_updated_at"] = _timestamp()
            updated_entry = entry
            break

    if updated_entry is None:
        return None

    _write_all_entries(entries)

    return updated_entry
