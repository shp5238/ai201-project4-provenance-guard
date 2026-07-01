import json

import audit_logger
from audit_logger import mark_classification_under_review, read_log


def test_mark_classification_under_review_updates_original_entry(tmp_path, monkeypatch):
    log_path = tmp_path / "audit_log.jsonl"
    monkeypatch.setattr(audit_logger, "LOG_PATH", log_path)

    original_entry = {
        "content_id": "content-1",
        "creator_id": "creator-1",
        "attribution": "likely_ai",
        "confidence": 0.8,
        "status": "classified"
    }

    log_path.write_text(json.dumps(original_entry) + "\n")

    updated = mark_classification_under_review(
        content_id="content-1",
        creator_id="creator-1",
        reasoning="I wrote this myself."
    )

    entries = read_log()

    assert updated["status"] == "under_review"
    assert updated["appeal_filed"] is True
    assert updated["creator_reasoning"] == "I wrote this myself."
    assert len(entries) == 1
    assert entries[0]["status"] == "under_review"
    assert entries[0]["appeal_filed"] is True
    assert entries[0]["creator_reasoning"] == "I wrote this myself."
    assert "appeal_updated_at" in entries[0]


def test_mark_classification_under_review_returns_none_for_unknown_content(
    tmp_path,
    monkeypatch
):
    log_path = tmp_path / "audit_log.jsonl"
    monkeypatch.setattr(audit_logger, "LOG_PATH", log_path)

    original_entry = {
        "content_id": "content-1",
        "creator_id": "creator-1",
        "attribution": "likely_ai",
        "confidence": 0.8,
        "status": "classified"
    }

    log_path.write_text(json.dumps(original_entry) + "\n")

    updated = mark_classification_under_review(
        content_id="missing-content",
        creator_id="creator-1",
        reasoning="I wrote this myself."
    )

    entries = read_log()

    assert updated is None
    assert entries[0]["status"] == "classified"
