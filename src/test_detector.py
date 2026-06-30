# Testing code here
import pytest

from detector import (
    clean_words,
    find_lexical_diversity,
    find_sentence_variation,
    find_ngram_overlap,
    find_stylometry,
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


def test_classify_text_returns_expected_keys():
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
    assert "metrics" in result


def test_metrics_are_returned():
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