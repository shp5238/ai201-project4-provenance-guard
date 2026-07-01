# Testing code here
import pytest

from detector import (
    clean_words,
    find_lexical_diversity,
    find_sentence_variation,
    find_ngram_overlap,
    find_stylometry,
    find_weighted_human_score,
    classify_text,
)


def test_clean_words_removes_punctuation_and_lowercases():
    words = clean_words("Hello, HELLO! This is a test.")
    assert words == ["hello", "hello", "this", "is", "a", "test"]


def test_empty_text_classification_returns_error():
    result = classify_text("")

    assert result["status"] == "error"
    assert result["message"] == "Text is required."


def test_short_text_is_uncertain():
    result = classify_text("Hello world", creator_id="test-user")

    assert result["status"] == "classified"
    assert result["attribution"] == "uncertain"
    assert result["human_score"] == 0.5
    assert result["confidence"] == 0.1


def test_lexical_diversity_empty_text_returns_neutral_score():
    assert find_lexical_diversity("") == 0.5


def test_lexical_diversity_repeated_words():
    score = find_lexical_diversity("dog dog cat")

    assert score == pytest.approx(2 / 3)


def test_sentence_variation_single_sentence_returns_zero():
    score = find_sentence_variation("This is only one sentence.")

    assert score == 0.0


def test_sentence_variation_multiple_sentences_returns_valid_range():
    score = find_sentence_variation(
        "Short sentence. This is a much longer sentence with many more words."
    )

    assert 0.0 <= score <= 1.0


def test_ngram_overlap_no_repetition():
    score = find_ngram_overlap("this sentence has no repeated bigrams", n=2)

    assert score == 0.0


def test_ngram_overlap_with_repetition():
    score = find_ngram_overlap("hello world hello world hello world", n=2)

    assert score > 0.0


def test_ngram_overlap_when_text_shorter_than_n():
    score = find_ngram_overlap("hello", n=2)

    assert score == 0.0


def test_stylometry_score_is_between_zero_and_one():
    text = (
        "I've been thinking a lot about remote work lately. "
        "There are genuine tradeoffs with flexibility and no commute on one side. "
        "But there are also problems like isolation and blurred boundaries."
    )

    score = find_stylometry(text)

    assert 0.0 <= score <= 1.0


def test_classify_text_returns_expected_keys(monkeypatch):
    monkeypatch.setattr("detector.has_groq_api_key", lambda: True)
    monkeypatch.setattr("detector.find_perplexity_score", lambda text: 0.5)

    text = (
        "I've been thinking a lot about remote work lately. "
        "There are genuine tradeoffs with flexibility and no commute on one side. "
        "But there are also problems like isolation and blurred work-life boundaries."
    )

    result = classify_text(text, creator_id="test-user")

    assert result["status"] == "classified"
    assert result["creator_id"] == "test-user"

    assert "human_score" in result
    assert "confidence" in result
    assert "attribution" in result
    assert "label" in result
    assert "signal_scores" in result
    assert "metrics" in result


def test_weighted_human_score_combines_perplexity_and_stylometry(monkeypatch):
    monkeypatch.setattr("detector.has_groq_api_key", lambda: True)
    monkeypatch.setattr("detector.find_perplexity_score", lambda text: 0.9)
    monkeypatch.setattr("detector.find_stylometry", lambda text: 0.3)

    result = find_weighted_human_score("This is long enough to score.")

    assert result["human_score"] == pytest.approx(0.66)
    assert result["perplexity_score"] == 0.9
    assert result["stylometry_score"] == 0.3


def test_weighted_human_score_uses_only_stylometry_without_groq_key(monkeypatch):
    monkeypatch.setattr("detector.has_groq_api_key", lambda: False)
    monkeypatch.setattr("detector.find_stylometry", lambda text: 0.3)

    result = find_weighted_human_score("This is long enough to score.")

    assert result["human_score"] == 0.3
    assert result["perplexity_score"] is None
    assert result["stylometry_score"] == 0.3
    assert result["perplexity_weight"] == 0.0
    assert result["stylometry_weight"] == 1.0
    assert (
        result["message"]
        == "This analysis is only using stylometry as a Grok API key has not been provided, so accuracy can vary."
    )


def test_metrics_are_returned(monkeypatch):
    monkeypatch.setattr("detector.has_groq_api_key", lambda: True)
    monkeypatch.setattr("detector.find_perplexity_score", lambda text: 0.5)

    text = (
        "This is a longer test paragraph. "
        "It has enough words to pass the short text check. "
        "The detector should return the metric values."
    )

    result = classify_text(text)

    metrics = result["metrics"]

    assert "lexical_diversity" in metrics
    assert "sentence_variation" in metrics
    assert "bigram_overlap" in metrics
    assert "trigram_overlap" in metrics


def test_signal_scores_are_returned(monkeypatch):
    monkeypatch.setattr("detector.has_groq_api_key", lambda: True)
    monkeypatch.setattr("detector.find_perplexity_score", lambda text: 0.75)
    monkeypatch.setattr("detector.find_stylometry", lambda text: 0.25)

    text = (
        "This is a longer test paragraph. "
        "It has enough words to pass the short text check. "
        "The detector should return the signal scores."
    )

    result = classify_text(text)
    signal_scores = result["signal_scores"]

    assert result["human_score"] == 0.55
    assert signal_scores["perplexity_score"] == 0.75
    assert signal_scores["stylometry_score"] == 0.25
    assert signal_scores["perplexity_weight"] == 0.6
    assert signal_scores["stylometry_weight"] == 0.4


def test_classify_text_returns_message_without_groq_key(monkeypatch):
    monkeypatch.setattr("detector.has_groq_api_key", lambda: False)
    monkeypatch.setattr("detector.find_stylometry", lambda text: 0.25)

    text = (
        "This is a longer test paragraph. "
        "It has enough words to pass the short text check. "
        "The detector should return the fallback message."
    )

    result = classify_text(text)

    assert result["human_score"] == 0.25
    assert result["signal_scores"]["perplexity_score"] is None
    assert result["signal_scores"]["perplexity_weight"] == 0.0
    assert result["signal_scores"]["stylometry_weight"] == 1.0
    assert (
        result["message"]
        == "This analysis is only using stylometry as a Grok API key has not been provided, so accuracy can vary."
    )
