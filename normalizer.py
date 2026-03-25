"""LLM Normalization — sends raw story text to Claude, returns structured JSON."""

import json
import re

import anthropic

import config

_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

_SYSTEM_PROMPT = """\
You are a data extraction assistant. The user will give you raw text and a link scraped from an Instagram story posted by @zero2sudo, a CS opportunity aggregator.

Your job is to classify the story and, if relevant, extract structured information.

Classification rules:
- "internship": story promotes a student internship or new grad role
- "hackathon": story promotes a hackathon or coding competition
- "skip": everything else (advice, DM screenshots, general tips, events, jobs, etc.)

If category is "skip", return ONLY: {"category": "skip"}
If category is "internship" or "hackathon", return the full schema below.

Rules for full extraction:
- Always return ONLY a valid JSON object, no markdown fences, no prose.
- If a field cannot be determined, use null.
- deadline should be YYYY-MM-DD if detectable, otherwise null
- summary should be 1-2 sentences, clear and professional
- For link_url, use the provided detected link — do not invent one.

JSON schema:
{
  "category": "internship" | "hackathon",
  "company": string | null,
  "title": string | null,
  "deadline": string | null,
  "location": string | null,
  "link_url": string | null,
  "summary": string | null
}
"""

_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _strip_fences(text: str) -> str:
    match = _FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def normalize(account: str, captured_at: str, raw_text: str, links: list[str]) -> dict:
    """
    Call Claude to extract structured fields from raw story text.
    Always returns a dict with the full schema (null values for missing fields).
    """
    link_hint = f"\nDetected links: {', '.join(links)}" if links else ""
    user_message = f"Source account: @{account}\n\nRaw story text:\n{raw_text}{link_hint}"

    base = {
        "source_account": account,
        "captured_at": captured_at,
        "raw_text": raw_text,
        "link_url": links[0] if links else None,
        "category": "other",
        "company": None,
        "title": None,
        "deadline": None,
        "location": None,
        "summary": None,
    }

    try:
        response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        raw_response = response.content[0].text
        cleaned = _strip_fences(raw_response)
        extracted = json.loads(cleaned)

        # Merge extracted fields into base (extracted fields win)
        base.update({k: v for k, v in extracted.items() if k in base})

        # If Claude found a link_url but we already have one from DOM, prefer Claude's
        if extracted.get("link_url"):
            base["link_url"] = extracted["link_url"]

    except json.JSONDecodeError as exc:
        print(f"[normalizer] JSON parse failed: {exc}. Raw response: {raw_response!r}")
    except Exception as exc:
        print(f"[normalizer] API call failed: {exc}")

    return base
