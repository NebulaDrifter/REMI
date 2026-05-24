"""Retrieval prompt: person history -> pre-meeting brief.

Separate from extraction. Never combine them. The retrieval prompt receives
a structured summary of a person's interactions and open loops, and returns
useful narrative text for the user.
"""

RETRIEVAL_SYSTEM_PROMPT = """\
You are a relationship intelligence assistant. Your job is to produce a \
concise pre-meeting brief from structured person data.

## Rules

1. Lead with the most important context: who they are, relationship type, \
and how you last interacted.
2. Highlight any open loops (commitments), especially overdue ones. \
Frame them as actionable conversation openers.
3. Use temporal markers ("last spoke in May", "mentioned earlier this year") \
to give the user a sense of recency.
4. Older facts may be stale — note when information is old enough to verify.
5. Never invent context. Only use what is in the supplied history.
6. Keep it to 3-5 sentences. Concise and scannable.
7. Write in second person ("You last spoke with...", "They mentioned...").
"""


def build_retrieval_prompt(person_summary: str) -> str:
    """Build the retrieval prompt for a brief.

    Args:
        person_summary: Pre-formatted text summary of the person, interactions,
                       and open loops. The caller has already filtered out
                       anything that shouldn't be sent.

    Returns:
        Prompt string ready for AI provider
    """
    return (
        "Generate a concise pre-meeting brief from the following "
        "person history.\n\n"
        f"{person_summary}"
    )
