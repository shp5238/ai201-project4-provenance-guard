import statistics
import re
from collections import Counter
import math

from perplexity import find_perplexity_score, has_groq_api_key


PERPLEXITY_WEIGHT = 0.6
STYLOMETRY_WEIGHT = 0.4
MISSING_GROQ_KEY_MESSAGE = (
    "This analysis is only using stylometry as a Grok API key has not been "
    "provided, so accuracy can vary."
)


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


def find_weighted_human_score(text):
    stylometry_score = find_stylometry(text)

    if not has_groq_api_key():
        return {
            "human_score": stylometry_score,
            "perplexity_score": None,
            "stylometry_score": stylometry_score,
            "perplexity_weight": 0.0,
            "stylometry_weight": 1.0,
            "message": MISSING_GROQ_KEY_MESSAGE
        }

    perplexity_score = find_perplexity_score(text)

    if perplexity_score is None:
        return {
            "human_score": stylometry_score,
            "perplexity_score": None,
            "stylometry_score": stylometry_score,
            "perplexity_weight": 0.0,
            "stylometry_weight": 1.0,
            "message": MISSING_GROQ_KEY_MESSAGE
        }

    weighted_score = (
        (perplexity_score * PERPLEXITY_WEIGHT)
        + (stylometry_score * STYLOMETRY_WEIGHT)
    )

    return {
        "human_score": max(0.0, min(weighted_score, 1.0)),
        "perplexity_score": perplexity_score,
        "stylometry_score": stylometry_score,
        "perplexity_weight": PERPLEXITY_WEIGHT,
        "stylometry_weight": STYLOMETRY_WEIGHT,
        "message": None
    }


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

    signal_scores = find_weighted_human_score(text)
    human_score = signal_scores["human_score"]

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

    response = {
        "status": "classified",
        "creator_id": creator_id,
        "human_score": round(human_score, 3),
        "confidence": round(confidence, 3),
        "attribution": attribution,
        "label": label,
        "signal_scores": {
            "perplexity_score": (
                round(signal_scores["perplexity_score"], 3)
                if signal_scores["perplexity_score"] is not None
                else None
            ),
            "stylometry_score": round(signal_scores["stylometry_score"], 3),
            "perplexity_weight": signal_scores["perplexity_weight"],
            "stylometry_weight": signal_scores["stylometry_weight"]
        },
        "metrics": {
            "lexical_diversity": round(find_lexical_diversity(text), 3),
            "sentence_variation": round(find_sentence_variation(text), 3),
            "bigram_overlap": round(find_ngram_overlap(text, 2), 3),
            "trigram_overlap": round(find_ngram_overlap(text, 3), 3)
        }
    }

    if signal_scores["message"]:
        response["message"] = signal_scores["message"]

    return response
