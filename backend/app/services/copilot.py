"""Optional LLM explainer. Disabled unless LLM_ENABLED=true and GEMINI_API_KEY is set.

It only rephrases structured facts already computed by the platform. It cannot call tools,
approve anything, change schedules or produce numbers that are not in the supplied context.
Never enable it for restricted data: the request leaves the network.
"""
import json

import httpx

from app.config import settings

SYSTEM = ("You explain outputs of an aircraft maintenance decision-support prototype. Use ONLY the JSON facts "
          "provided. Never invent numbers, procedures, sensor readings or approvals. If the facts do not answer the "
          "question, say so. State that outputs are advisory and not airworthiness decisions. Max 180 words.")


def enabled() -> bool:
    return settings.llm_enabled and bool(settings.gemini_api_key)


def explain(question: str, facts: dict, client: httpx.Client | None = None) -> str:
    if not enabled():
        raise RuntimeError("copilot disabled")
    body = {"system_instruction": {"parts": [{"text": SYSTEM}]},
            "contents": [{"role": "user", "parts": [{"text": f"FACTS:\n{json.dumps(facts, default=str)[:20000]}\n\nQUESTION: {question}"}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 400}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    c = client or httpx.Client(timeout=20)
    r = c.post(url, json=body, headers={"x-goog-api-key": settings.gemini_api_key})
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]
