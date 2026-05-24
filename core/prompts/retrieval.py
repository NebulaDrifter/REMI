"""Retrieval prompt: person history → pre-meeting brief.

Separate from extraction. Never combine them. The retrieval prompt receives
a structured summary of a person's interactions and open loops, and returns
useful narrative text for the user.
"""

# TODO (Phase 5): Iterate on this prompt with both Anthropic and Ollama adapters.
#
# The retrieval prompt should:
# - Receive a structured Person + interactions list + open loops list
# - Produce ~3-5 sentences of useful brief text
# - Lead with most important context (relationship type, last interaction)
# - Highlight any overdue open loops as actionable items
# - Use temporal markers ("last spoke in May", "earlier this year")
# - Distinguish older facts from recent ones
# - Never invent context — only use what's in the supplied history

RETRIEVAL_SYSTEM_PROMPT = """\
TODO: Write retrieval prompt in Phase 5.

Key design notes:
- Input is a structured person history blob, not raw user input
- Output is narrative text (1-2 short paragraphs)
- Mark open loops as actionable
- Respect temporal context — old facts may be stale
"""


def build_retrieval_prompt(person_summary: str) -> str:
    """Build the retrieval prompt for a brief.

    Args:
        person_summary: Pre-formatted text summary of the person, interactions,
                       and open loops. The caller (likely retrieval logic in core/)
                       has already filtered out anything that shouldn't be sent.

    Returns:
        Prompt string ready for AI provider
    """
    # TODO (Phase 5): Implement after retrieval prompt is written
    return person_summary
