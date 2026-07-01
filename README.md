# Provenance Guard
By Shreya Pasupuleti

Provenance Guard is a backend system that any creative sharing platform could plug into to classify submitted content, score confidence in that classification, surface a transparency label to users, and handle appeals from creators who believe they've been misclassified.

Full design rationale, edge cases, and AI-tool prompting plan live in [planning.md](planning.md). This README documents the actual implementation.

To use, update .env.example with your API key!

## Architecture Overview

A submission's raw text is sent to `POST /submit`, scored independently by two signals — an LLM semantic read (Groq) and a stylometric structural read (pure Python) — combined into a single `human_score`, converted into a `confidence` value, and mapped to one of three attribution labels via fixed thresholds. Every classification gets a `content_id` and is written to `src/audit_log.jsonl` before the response returns. An appeal (`POST /appeal`) references that `content_id`, locates the original log entry, and mutates it in place — status, appeal flag, reasoning, timestamp — rather than creating a new classification. `GET /log` exposes the log read-only. See the `## Architecture` diagram in [planning.md](planning.md) for the full flow.

## Detection Signals

**Signal 1 — LLM classification (Groq, `llama-3.3-70b-versatile`)**, `src/perplexity.py::find_perplexity_score`
- Measures: holistic semantic/stylistic read — specificity, lived experience, rhythm, over-smoothing, generic phrasing.
- Chosen because it captures meaning and voice that word-level statistics can't.
- Output: float 0–1 (`human_likelihood`), 0 = AI, 1 = human.
- Misses: it's one model's opinion with no ground truth; can be fooled by a good human-style prompt, or penalize plain human writing that happens to read generically.

**Signal 2 — Stylometric heuristics (pure Python)**, `src/detector.py::find_stylometry`
- Sub-metrics: lexical diversity (unique/total words), sentence-length variation (stdev, tanh-scaled), bigram overlap, trigram overlap.
- Chosen because it's a structural counterweight — independent of the LLM's judgment, cheap, and deterministic.
- Output: float 0–1, computed as an evidence ratio (`evidence_human / (evidence_human + evidence_ai)`), not a plain average.
- Misses: purely structural — a human writer with a flat or repetitive style (children's writing, transcribed speech) scores like AI. Noisy on very short text.

**Combination:** `human_score = perplexity_score * 0.6 + stylometry_score * 0.4` (`src/detector.py::find_weighted_human_score`). The LLM signal is weighted higher because it captures semantics the heuristics can't; stylometry acts as a structural check. If no Groq key is set or the API call raises, weight collapses to stylometry-only (1.0) and a `message` field notes the degraded mode.

## Confidence Scoring

`confidence = abs(human_score - 0.5) * 2` — distance from maximum uncertainty (0.5), scaled to 0–1. A `human_score` near 0.5 (genuinely unclear) yields a low confidence near 0; a `human_score` near 0 or 1 yields confidence near 1.

Attribution thresholds (`src/detector.py::classify_text`):
- `human_score <= 0.3` → `likely_ai`
- `human_score >= 0.8` → `likely_human`
- otherwise → `uncertain`

**Validation:** tested with real submissions through the running server. Two actual log entries with noticeably different confidence:

| Case | human_score | confidence | attribution | label |
|---|---|---|---|---|
| High-confidence | 0.966 | 0.931 | `likely_human` | "Likely human-created" |
| Low-confidence | 0.594 | 0.187 | `uncertain` | "We're not sure who wrote this." |

The gap between 0.931 and 0.187 confidence on real submissions shows the score isn't a constant — it moves meaningfully with how far the combined signal sits from the 0.5 midpoint.

## Transparency Label

Exact text returned in the `label` field, by `attribution`:

| Variant | Exact label text |
|---|---|
| High-confidence AI | `"Likely AI-created"` |
| High-confidence human | `"Likely human-created"` |
| Uncertain | `"We're not sure who wrote this."` |

(A fourth, non-required edge case also exists: submissions under 10 words return `"Text is too short to classify confidently."` with a fixed low confidence of 0.1, since the signals are unreliable on that little text.)

## Appeals Workflow

`POST /appeal` (`src/app.py`) requires `content_id`, `creator_id`, `creator_reasoning`. `mark_classification_under_review` (`src/audit_logger.py`) finds the matching log entry (by `content_id` + `creator_id` + `status == "classified"`) and updates it in place: `status → "under_review"`, `appeal_filed → true`, `creator_reasoning` stored, `appeal_updated_at` stamped. Returns 404 if no matching classified entry exists. A reviewer opening `GET /log` sees the appealed entry inline with those fields populated — there's no separate appeal-only view (see Deviations below).

## Rate Limiting

Applied via Flask-Limiter on `POST /submit`:

```python
@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
```

**Reasoning:** a genuine writer submitting their own drafts rarely posts more than a couple of pieces per minute, so 10/minute leaves headroom for retries and edits while still blocking a script that floods the endpoint. 100/day caps sustained abuse from a single IP without punishing a heavy but legitimate user.

**Evidence** (12 rapid requests sent to a running local server):

```
200
200
200
200
200
200
200
200
200
200
429
429
```

First 10 succeed, requests 11–12 are rejected with `429` — confirms the limit fires as configured.

## Audit Log

Structured JSONL at `src/audit_log.jsonl`, one entry per line, written by `src/audit_logger.py`. `GET /log` returns the most recent entries as JSON. Sample entries (real, from the log):

```json
{"status": "classified", "creator_id": "frontend-user", "human_score": 0.966, "confidence": 0.931, "attribution": "likely_human", "label": "Likely human-created", "metrics": {"lexical_diversity": 0.86, "sentence_variation": 0.477, "bigram_overlap": 0.0, "trigram_overlap": 0.0}, "content_id": "f9db4442-d934-4163-a0b5-4e08b95d5122", "timestamp": "2026-06-30T22:50:42.925855+00:00"}
{"status": "under_review", "creator_id": "frontend-user", "human_score": 0.594, "confidence": 0.187, "attribution": "uncertain", "label": "We're not sure who wrote this.", "signal_scores": {"perplexity_score": 0.9, "stylometry_score": 0.134, "perplexity_weight": 0.6, "stylometry_weight": 0.4}, "metrics": {"lexical_diversity": 0.75, "sentence_variation": 0.094, "bigram_overlap": 0.018, "trigram_overlap": 0.0}, "content_id": "7650c515-b569-470b-920c-f834d8fdabe1", "timestamp": "2026-07-01T04:14:00.951818+00:00", "appeal_filed": true, "creator_reasoning": "no no it is ai generated.", "appeal_updated_at": "2026-07-01T04:15:51.150666+00:00"}
{"status": "under_review", "creator_id": "frontend-user", "human_score": 0.138, "confidence": 0.723, "attribution": "likely_ai", "label": "Likely AI-created", "metrics": {"lexical_diversity": 0.742, "sentence_variation": 0.101, "bigram_overlap": 0.067, "trigram_overlap": 0.034}, "content_id": "5ec2fe64-b919-4b92-96b3-49b60353dd70", "timestamp": "2026-06-30T22:43:03.954709+00:00", "appeal_filed": true, "creator_reasoning": "nope I wrote it myself", "appeal_updated_at": "2026-06-30T22:43:12.023919+00:00"}
```

Log has 18 entries total, including 2 appeals in the sample above.

## Known Limitations

**Repetitive, simple-vocabulary human writing scores like AI.** A children's poem, a mantra-style piece, or transcribed casual speech with heavy word repetition produces low lexical diversity and low sentence-length variance — exactly the pattern `find_stylometry` treats as AI-smoothed. The heuristics have no way to tell "simple because AI over-smoothed" from "simple because that's the genre or voice," so this is a direct blind spot of Signal 2, not a generic accuracy gap.

**A Groq API failure is indistinguishable from a genuine 0.5 verdict.** `find_perplexity_score` catches all exceptions (timeout, bad JSON, network error) and returns `0.5`, which is scored identically to the model actually saying "50/50 uncertain." Only a *missing* API key is flagged distinctly (via the `message` field); a transient outage silently degrades to that same neutral score with no indication anything went wrong.

## Spec Reflection

The spec's requirement to write out label thresholds and text *before* touching code ([planning.md](planning.md)) directly shaped the implementation — deciding `0.3`/`0.8` as attribution cutoffs up front made `classify_text` a straightforward threshold check instead of something tuned after the fact by eyeballing outputs.

Where implementation diverged: the plan's original framing (per the false-positive-asymmetry hint) called for the `likely_ai` cutoff to require *at least as much* evidence as `likely_human`, since mislabeling a human as AI is the worse error. As shipped, `likely_ai` fires 0.2 away from the 0.5 midpoint (at 0.3) while `likely_human` requires 0.3 away (at 0.8) — meaning the system is currently *more* willing to call something AI than human, the opposite of the intended asymmetry. This was caught during planning review, not fixed in code; flagged here rather than silently left unaddressed.

## Deviations from the Plan

- **`likely_ai` threshold is less conservative than intended.** As described in Spec Reflection above: `likely_ai` needs only a 0.2 distance from 0.5 (score ≤ 0.3) while `likely_human` needs a 0.3 distance (score ≥ 0.8). The original design intent — protect against false-positive AI accusations — would call for the opposite (a *stricter* bar for `likely_ai`, e.g. moving that cutoff to ≤ 0.2 or lower, or symmetric distances in the safer direction).
- **Label text doesn't surface the confidence number itself.** The plan called for labels that make confidence "meaningful to a non-technical reader." The current three strings communicate attribution but not degree (e.g. `"Likely AI-created"` reads the same whether `human_score` is 0.29 or 0.01). An ideal version would interpolate confidence into the string, e.g. `"Likely AI-created (high confidence)"` vs. `(borderline)`.
- **No dedicated appeal-review view.** The plan's appeals workflow described what "a human reviewer would see when they open the appeal queue." No `/appeals` or `/log?status=under_review` filter exists — a reviewer has to scan the full `GET /log` output and check `status` manually.
- **Silent fallback on Groq failure.** As noted in Known Limitations, an API error and a genuine 0.5 verdict both land on the same score with the same `message` behavior (only a missing key is flagged). The plan implied any degraded-signal state would be visible in the response; a transient failure currently is not.

## AI Usage

1. **Directed:** asked an AI tool to draft the Flask route skeleton for `/submit` and `/appeal` from the [planning.md](planning.md) architecture diagram and detection-signals section. **Produced:** working route stubs with request validation. **Revised:** the generated appeal-matching logic didn't check `status == "classified"` before allowing an appeal, which would have let the same content be appealed twice with a status flip each time — added that guard so a second appeal on an already-appealed item returns 404 instead of silently re-logging.
2. **Directed:** given my preliminary code from my independent research, I asked an AI tool to generate the stylometric scoring function combining lexical diversity, sentence variance, and n-gram overlap into one score per the Detection Signals section. **Produced:** a version that averaged the four sub-metrics directly. **Revised:** a plain average let a single degenerate metric (e.g. zero bigram overlap on very short text) dominate the score; replaced it with the evidence-ratio approach (`evidence_human / (evidence_human + evidence_ai)`) actually in `find_stylometry`, which weights metrics multiplicatively so no single signal alone can push the score to an extreme.
