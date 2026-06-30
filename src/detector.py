import statistics
import re
from collections import Counter
import math


def clean_words(text):
    return re.findall(r"\b\w+\b", text.lower())


def find_lexical_diversity(text=""):
    words = clean_words(text)

    if len(words) == 0:
        return 0.5

    unique_words = len(set(words))
    total_words = len(words)

    return unique_words / total_words


def find_sentence_variation(text, scale_factor=15):
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) < 2:
        return 0.0

    sentence_lengths = [len(clean_words(sentence)) for sentence in sentences]

    if len(sentence_lengths) < 2:
        return 0.0

    variation = statistics.stdev(sentence_lengths)

    return math.tanh(variation / scale_factor)


def find_ngram_overlap(text, n=2):
    words = clean_words(text)

    if len(words) < n:
        return 0.0

    grams = [
        tuple(words[i:i + n])
        for i in range(len(words) - n + 1)
    ]

    counts = Counter(grams)

    repeated = sum(
        count - 1
        for count in counts.values()
        if count > 1
    )

    return repeated / len(grams)


def find_stylometry(text):
    lex_div = find_lexical_diversity(text)
    sent_var = find_sentence_variation(text)
    bigram_rep = find_ngram_overlap(text, n=2)
    trigram_rep = find_ngram_overlap(text, n=3)

    if sent_var < 0.35:
        p_human_var = sent_var * 0.1
    else:
        p_human_var = sent_var

    p_human_bigram = max(0.1, min(0.7, 1.0 - bigram_rep))
    p_human_trigram = max(0.1, min(0.7, 1.0 - trigram_rep))
    p_human_lex = max(0.1, min(0.85, lex_div))

    evidence_human = (
        p_human_lex
        * p_human_var
        * p_human_bigram
        * p_human_trigram
    )

    evidence_ai = (
        (1.0 - p_human_lex)
        * (1.0 - p_human_var)
        * (1.0 - p_human_bigram)
        * (1.0 - p_human_trigram)
    )

    total_evidence = evidence_human + evidence_ai

    if total_evidence == 0:
        return 0.5

    final_score = evidence_human / total_evidence

    return max(0.0, min(final_score, 1.0))


def classify_text(text, creator_id="anonymous"):
    if text is None or text.strip() == "":
        return {
            "status": "error",
            "message": "Text is required."
        }

    words = clean_words(text)

    if len(words) < 10:
        return {
            "status": "classified",
            "creator_id": creator_id,
            "human_score": 0.5,
            "confidence": 0.1,
            "attribution": "uncertain",
            "label": "Text is too short to classify confidently."
        }

    human_score = find_stylometry(text)

    if human_score <= 0.3:
        attribution = "likely_ai"
        label = "Likely AI-created"
    elif human_score >= 0.8:
        attribution = "likely_human"
        label = "Likely human-created"
    else:
        attribution = "uncertain"
        label = "We're not sure who wrote this."

    confidence = abs(human_score - 0.5) * 2

    return {
        "status": "classified",
        "creator_id": creator_id,
        "human_score": round(human_score, 3),
        "confidence": round(confidence, 3),
        "attribution": attribution,
        "label": label,
        "metrics": {
            "lexical_diversity": round(find_lexical_diversity(text), 3),
            "sentence_variation": round(find_sentence_variation(text), 3),
            "bigram_overlap": round(find_ngram_overlap(text, 2), 3),
            "trigram_overlap": round(find_ngram_overlap(text, 3), 3)
        }
    }