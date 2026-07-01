# Provenance Guard — Planning

## Detection Signals

**Signal 1 — LLM classification (Groq, `llama-3.3-70b-versatile`)**
- File: `src/perplexity.py`, function `find_perplexity_score(text)`.
- Measures: holistic semantic/stylistic read — specificity, lived experience, rhythm, over-smoothing, generic phrasing.
- Output: float 0–1 (`human_likelihood`), 0 = AI, 1 = human. Model returns JSON `{human_likelihood, reasoning}`, clamped to [0,1].
- Blind spot: opinion of one model, no ground truth. Can be fooled by a good human imitation prompt, or penalize genuinely plain human writing that "reads" generic. On API failure it silently returns `0.5` (max uncertainty) rather than erroring — see Divergence note below.

**Signal 2 — Stylometric heuristics (pure Python)**
- File: `src/detector.py`, function `find_stylometry(text)`.
- Sub-metrics: lexical diversity (unique/total words), sentence-length variation (stdev, tanh-scaled), bigram overlap, trigram overlap.
- Output: float 0–1, via an evidence-ratio (`evidence_human / (evidence_human + evidence_ai)`), not a simple average.
- Blind spot: purely structural — a human writer with a flat, repetitive style (e.g. simple children's writing, transcribed speech) scores like AI. Short text produces noisy stats (mitigated by the <10-word floor below).

**Combination**
- `human_score = perplexity_score * 0.6 + stylometry_score * 0.4` (`find_weighted_human_score` in `detector.py`).
- LLM weighted higher (0.6) because it captures semantics the heuristics can't; stylometry (0.4) acts as a structural check/counterweight.
- If no Groq key or the API call fails, weight collapses to stylometry-only (1.0) and a `message` field flags the degraded mode — system still classifies rather than erroring.

**Ideal case (divergence note):** the spec's default pairing description treats both signals as independent 0–1 scores combined by a documented weighting. That's what's implemented. One divergence from an "ideal" version: a failed Groq call falls back to `0.5` inside `find_perplexity_score` on any exception (network, bad JSON, etc.), which is indistinguishable from a model genuinely saying "uncertain." Ideally, an API failure would be logged/flagged distinctly from a genuine 0.5 verdict — right now `has_groq_api_key()` only detects a *missing* key, not a failed call, so a transient Groq outage silently degrades scoring without the `message` fallback firing.

## Uncertainty Representation

- `confidence = abs(human_score - 0.5) * 2` — distance from maximum uncertainty (0.5), scaled to 0–1. A `human_score` of 0.51 → confidence ≈ 0.02 (low); 0.95 → confidence 0.9 (high). This satisfies the spec requirement that 0.51 and 0.95 confidence must read differently.
- Attribution thresholds (in `classify_text`): `human_score <= 0.3` → `likely_ai`; `human_score >= 0.8` → `likely_human`; otherwise → `uncertain`.
- **Ideal case (divergence note):** thresholds are asymmetric around 0.5 (0.3 vs 0.8, not e.g. 0.3/0.7 symmetric). This is intentional, not a bug: per the false-positive-asymmetry hint, mislabeling a human as AI is worse than the reverse, so the bar to call something `likely_ai` (≤0.3) is stricter/farther from center than the bar for `likely_human` (≥0.8 is actually the *farther* bound — meaning "likely_human" requires stronger evidence than "likely_ai" at first glance). This should be re-examined: as coded, `likely_human` requires a *more* confident score (0.8) than `likely_ai` needs (0.3, i.e. only 0.2 away from center vs 0.8 needing 0.3 away — actually 0.3 away from 0.5 either direction is symmetric distance). Re-checked: 0.5-0.3=0.2 and 0.8-0.5=0.3 — thresholds are NOT symmetric distances from 0.5. `likely_ai` fires at just 0.2 away from center; `likely_human` needs 0.3 away. That means the system is currently *more* trigger-happy calling something AI than human — the opposite of the safer design the hint recommends. Ideal fix: mirror the `likely_ai` cutoff to 0.7 (symmetric) or push it down to ≤0.2 so both labels require equal evidence, or explicitly widen the AI-side band further to bias toward `uncertain`/`likely_human` on the margin.
- Text under 10 words short-circuits to a hardcoded `human_score: 0.5, confidence: 0.1, attribution: "uncertain"` in `classify_text` — an explicit low-confidence floor for insufficient data, not sent through the signals at all.

## Transparency Label Design

Exact strings returned in the `label` field, keyed by `attribution`:

| attribution | label text |
|---|---|
| `likely_ai` | `"Likely AI-created"` |
| `likely_human` | `"Likely human-created"` |
| `uncertain` | `"We're not sure who wrote this."` |
| (short-text edge case) | `"Text is too short to classify confidently."` |

**Ideal case (divergence note):** spec asks the label to "make the confidence level meaningful to a non-technical reader." Current labels communicate the *attribution* but not the *confidence number* itself (e.g. don't say "moderately confident" vs "very confident"). Ideal version would interpolate confidence into the string, e.g. `"Likely AI-created (high confidence)"` vs `"Likely AI-created (low confidence)"` for two different `likely_ai` scores. Not yet implemented — README should note this as a known limitation.

## Appeals Workflow

- `POST /appeal` (`src/app.py`) requires `content_id`, `creator_id`, `creator_reasoning`.
- `mark_classification_under_review` (`src/audit_logger.py`) finds the matching log entry (matched on `content_id` + `creator_id` + `status == "classified"`), and in place: sets `status = "under_review"`, `appeal_filed = True`, stores `creator_reasoning`, stamps `appeal_updated_at`.
- Returns 404 if no matching classified entry exists (already-appealed or wrong ID/creator).
- Reviewer view: `GET /log` returns the full entry list; an appealed entry is visible with `status: "under_review"`, `appeal_filed: true`, and `creator_reasoning` populated inline — no separate appeal queue endpoint exists.
- **Ideal case (divergence note):** spec's hint about "appeal queue" implies a reviewer-facing view distinct from the general log (e.g. `GET /log?status=under_review`). Currently a reviewer must scan all `/log` entries and filter by `status` client-side. Ideal version adds a query filter or a dedicated `/appeals` endpoint.

## Anticipated Edge Cases

1. **Repetitive, simple-vocabulary human writing** (e.g. a children's poem, a mantra-style piece, or transcribed casual speech with heavy word repetition) — low lexical diversity + low sentence variation will push `find_stylometry` toward the AI side, even though a human wrote it. Structural signal has no way to distinguish "simple by AI smoothing" from "simple by genre/voice."
2. **Very short submissions** (under 10 words) — caught by an explicit floor in `classify_text` that forces `uncertain` at 0.1 confidence rather than running the signals at all, because bigram/trigram/stdev stats are meaningless on tiny samples.
3. **Heavily edited AI output** (a human rewrites AI text sentence-by-sentence) — `find_perplexity_score` may catch this from tone, but stylometric heuristics look at surface structure only and can be pushed toward "human" by light edits, so the two signals can disagree; the 0.6/0.4 weighting means the LLM signal dominates in a disagreement.
4. **Groq API outage/timeout** — `find_perplexity_score` catches all exceptions and returns `0.5`, which is scored identically to a genuine LLM verdict of "uncertain." A grader/operator can't distinguish "the model said 50/50" from "the API call failed," since no error flag propagates from that path (only a missing-key case sets the `message` field).

## Architecture

```
                         POST /submit
                              |
                    {text, creator_id}
                              |
                              v
                     classify_text()
                     (src/detector.py)
                              |
        +---------------------+----------------------+
        |                                             |
        v                                             v
 find_perplexity_score()                      find_stylometry()
 (src/perplexity.py, Groq LLM)         (src/detector.py, pure Python)
  -> human_likelihood 0..1               -> lexical_diversity, sentence_variation,
                                             bigram/trigram overlap -> score 0..1
        |                                             |
        +---------------------+----------------------+
                              |
                 human_score = 0.6*LLM + 0.4*stylometry
                              |
                              v
                    confidence = |score-0.5|*2
                 attribution/label thresholds (0.3 / 0.8)
                              |
                              v
                content_id = uuid4() assigned
                              |
                              v
                    log_event() -> audit_log.jsonl
                              |
                              v
        response: {content_id, attribution, confidence,
                   label, signal_scores, metrics}


                         POST /appeal
                              |
            {content_id, creator_id, creator_reasoning}
                              |
                              v
              mark_classification_under_review()
              (src/audit_logger.py — finds matching
               log entry by content_id + creator_id)
                              |
                              v
        entry.status = "under_review", appeal_filed = true,
        creator_reasoning + appeal_updated_at written in place
                              |
                              v
        response: {content_id, status, classification_status,
                   appeal_filed, message}

                         GET /log
                              |
                              v
                read_log() -> last N entries from
                     audit_log.jsonl, as JSON
```

**Narrative:** A submission's raw text is scored independently by two signals — an LLM semantic read and a stylometric structural read — which are combined into one `human_score`, converted into a `confidence` distance-from-uncertainty value, and mapped to one of three attribution labels via fixed thresholds; every classification is assigned a `content_id` and written to the JSONL audit log before the response returns. An appeal references that same `content_id`, locates the original log entry, and mutates it in place (status, appeal flag, reasoning, timestamp) rather than creating a new classification — no re-scoring happens. Both flows converge on the same audit log, which `GET /log` exposes read-only for review/grading.

## AI Tool Plan

**M3 (submission endpoint + first signal):**
- Provide: Detection Signals section above (signal 1 description) + Architecture diagram (submission flow).
- Ask for: Flask app skeleton with `POST /submit` route stub, plus the `find_perplexity_score` function.
- Verify: call `find_perplexity_score` directly with 2–3 known human/AI snippets before wiring into the route; confirm it returns a float in [0,1] and handles a missing API key without crashing.

**M4 (second signal + confidence scoring):**
- Provide: Detection Signals section (signal 2) + Uncertainty Representation section + Architecture diagram.
- Ask for: `find_stylometry` function (lexical diversity, sentence variation, n-gram overlap) + the weighted-combination/confidence logic in `find_weighted_human_score` and `classify_text`.
- Verify: run both signals on the same 4+ test inputs (AI, human, two borderline) and confirm scores diverge meaningfully and thresholds (0.3/0.8) produce all 3 attribution categories, not just 2.

**M5 (production layer):**
- Provide: Transparency Label Design section + Appeals Workflow section + Architecture diagram (appeal flow).
- Ask for: label-mapping logic in `classify_text` + the `POST /appeal` endpoint and `mark_classification_under_review` helper.
- Verify: submit inputs that hit all 3 label variants; submit an appeal against a real `content_id` and confirm `GET /log` shows `status: "under_review"` and `creator_reasoning` populated; confirm a bad/duplicate `content_id` returns 404 instead of silently succeeding.
