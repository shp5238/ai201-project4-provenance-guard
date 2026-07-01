import json
import os
import re

from dotenv import load_dotenv
from groq import Groq


MODEL = "llama-3.3-70b-versatile"


SYSTEM_PROMPT = """
You are the LLM-based detection signal for Provenance Guard.
Assess whether the submitted text reads like human-written work or
AI-generated work. Focus on holistic semantic and stylistic patterns:
specificity, lived experience, rhythm, uniformity, generic phrasing,
and whether the writing feels over-smoothed.

Return only JSON with this exact schema:
{
  "human_likelihood": 0.0,
  "reasoning": "one short sentence"
}

human_likelihood must be a number from 0 to 1, where:
0 means very likely AI-generated,
0.5 means genuinely uncertain,
1 means very likely human-written.
"""


def _clamp_score(score):
    return max(0.0, min(float(score), 1.0))


def _extract_json_object(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)

    if match is None:
        raise ValueError("Groq response did not include a JSON object.")

    return json.loads(match.group(0))


def has_groq_api_key():
    load_dotenv()

    return bool(os.getenv("GROQ_API_KEY"))


def find_perplexity_score(text):
    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        return None

    client = Groq(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        result = _extract_json_object(content)

        return _clamp_score(result["human_likelihood"])
    except Exception:
        return 0.5
