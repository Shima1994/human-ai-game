import itertools
import re


def normalize_words(text):
    return re.findall(r"[a-z0-9]+", str(text).lower())


def _token_variants(token):
    variants = {token}
    if len(token) > 2:
        variants.add(f"{token}s")
        variants.add(f"{token}es")
    if token.endswith("y") and len(token) > 2:
        variants.add(f"{token[:-1]}ies")
    if token.endswith("ies") and len(token) > 3:
        variants.add(f"{token[:-3]}y")
    if token.endswith("es") and len(token) > 3:
        variants.add(token[:-2])
    if token.endswith("s") and len(token) > 3:
        variants.add(token[:-1])
    return variants


def mentions_board_word(text, board_words):
    if not str(text or "").strip():
        return False

    explanation_tokens = normalize_words(text)
    explanation_token_set = set(explanation_tokens)
    explanation_phrase = " ".join(explanation_tokens)

    for board_word in board_words or []:
        board_tokens = normalize_words(board_word)
        if not board_tokens:
            continue

        if len(board_tokens) == 1:
            base_token = board_tokens[0]
            variants = _token_variants(base_token)
            if explanation_token_set.intersection(variants):
                return True
            if len(base_token) >= 4 and any(
                token.startswith(base_token) for token in explanation_token_set
            ):
                return True
            continue

        exact_phrase = " ".join(board_tokens)
        if exact_phrase in explanation_phrase:
            return True

        for variant_tokens in itertools.product(*[_token_variants(token) for token in board_tokens]):
            if " ".join(variant_tokens) in explanation_phrase:
                return True

    return False
