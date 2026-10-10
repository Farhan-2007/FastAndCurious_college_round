import re
from difflib import SequenceMatcher
from typing import Optional


def _normalise_with_position_map(text: str) -> tuple[str, list[int]]:
    """
    Collapse runs of whitespace to one space while keeping a map from
    each normalised character back to its position in the original text.
    """
    normalised_characters = []
    original_positions = []

    index = 0

    while index < len(text):
        if text[index].isspace():
            # Treat consecutive spaces, tabs, or newlines as one space.
            while index < len(text) and text[index].isspace():
                index += 1

            normalised_characters.append(" ")
            # Map that normalised space to the start of the original whitespace.
            original_positions.append(index - 1)
        else:
            normalised_characters.append(text[index])
            original_positions.append(index)
            index += 1

    return "".join(normalised_characters), original_positions


def compute_span(claim_text: str, answer_text: str) -> Optional[dict]:
    """
    Find the start and end character positions of a claim in the answer.

    First tries an exact match, then a whitespace-normalised match.
    If neither succeeds, it returns the closest matching sentence only
    when the match is reasonably strong. Returns None if no safe match is found.
    """
    if not claim_text or not answer_text:
        return None

    # 1. Exact substring match.
    exact_start = answer_text.find(claim_text)
    if exact_start != -1:
        return {
            "start": exact_start,
            "end": exact_start + len(claim_text),
        }

    # 2. Match after collapsing whitespace, while mapping positions back
    #    to the original answer for accurate frontend highlighting.
    normalised_answer, position_map = _normalise_with_position_map(answer_text)
    normalised_claim, _ = _normalise_with_position_map(claim_text)

    normalised_claim = normalised_claim.strip()
    if normalised_claim:
        normalised_start = normalised_answer.find(normalised_claim)

        if normalised_start != -1:
            normalised_end = normalised_start + len(normalised_claim)

            original_start = position_map[normalised_start]
            original_end = position_map[normalised_end - 1] + 1

            return {
                "start": original_start,
                "end": original_end,
            }

    # 3. Fallback: find the sentence most similar to the claim.
    # Keep each sentence's original character positions.
    sentences = []

    for match in re.finditer(r"[^.!?]+(?:[.!?]+|$)", answer_text):
        sentence_start = match.start()
        sentence_end = match.end()
        sentence = match.group()

        # Trim whitespace but preserve the original positions.
        leading_spaces = len(sentence) - len(sentence.lstrip())
        trailing_trimmed = len(sentence.rstrip())

        trimmed_sentence = sentence.strip()
        if trimmed_sentence:
            start = sentence_start + leading_spaces
            end = sentence_start + trailing_trimmed
            sentences.append((trimmed_sentence, start, end))

    if not sentences:
        return None

    best_sentence, best_start, best_end = max(
        sentences,
        key=lambda item: SequenceMatcher(
            None,
            item[0].lower(),
            claim_text.strip().lower(),
        ).ratio(),
    )

    similarity = SequenceMatcher(
        None,
        best_sentence.lower(),
        claim_text.strip().lower(),
    ).ratio()

    # Avoid highlighting an unrelated sentence if the match is very weak.
    if similarity < 0.35:
        return None

    return {
        "start": best_start,
        "end": best_end,
    }


def _normalise_whitespace(text: str) -> str:
    """Collapse all whitespace runs to one space and trim the ends."""
    return " ".join(text.split())


def validate_quote(quote: str, pdf_chunks: list[dict]) -> tuple[bool, Optional[int]]:
    """
    Check whether an evidence quote exists in the extracted PDF text.

    Returns:
        (True, page_number) if the quote is found.
        (False, None) if it is empty or cannot be found.
    """
    if not isinstance(quote, str) or not quote.strip():
        return False, None

    normalised_quote = _normalise_whitespace(quote)

    for chunk in pdf_chunks:
        chunk_text = chunk.get("text", "")
        page_number = chunk.get("page")

        if not isinstance(chunk_text, str):
            continue

        normalised_chunk = _normalise_whitespace(chunk_text)

        if normalised_quote in normalised_chunk:
            return True, page_number

    return False, None