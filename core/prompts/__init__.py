"""Provider-agnostic prompts for REMI.

All prompts MUST work with any AI provider. No Anthropic-tuned XML hacks,
no OpenAI JSON-mode-specific quirks. The adapter handles provider-specific
formatting. The prompt itself is provider-neutral.

Two prompts only. Never combine them:
- extraction.py: raw user input → ExtractionResult
- retrieval.py: person history → pre-meeting brief text
"""
