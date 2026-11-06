"""Builds the system prompt: the full knowledge base first, then fixed rules.

SYSTEM_PROMPT is built once and never changes. Keeping it identical on every
request lets automatic prompt caching reuse it, so put nothing per-request in here.
"""
from app.core.config import GUIDELINES_PATH
from app.prompts.rules import OUTPUT_RULES

GUIDELINES = GUIDELINES_PATH.read_text(encoding="utf-8")

SYSTEM_PROMPT = (
    "=== KNOWLEDGE BASE ===\n" + GUIDELINES + "\n=== END KNOWLEDGE BASE ===\n\n" + OUTPUT_RULES
)
