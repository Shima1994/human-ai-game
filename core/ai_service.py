import json
import random
import re
import time

import streamlit as st
from openai import OpenAI

from core.constants import (
    AI_API_TIMEOUT_SECONDS,
    DEFAULT_CONDITION,
    GUESS_MODEL_NAME,
    HINT_MODEL_NAME,
    MAX_HINT_NUMBER,
    REFLECTION_MODEL_NAME,
    TARGET_COUNT,
)
from core.validation import mentions_board_word

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])


class AIClueGenerationError(RuntimeError):
    def __init__(self, message, *, attempts, last_raw, response_time_sec):
        super().__init__(message)
        self.attempts = attempts
        self.last_raw = last_raw
        self.response_time_sec = response_time_sec


def call_openai_chat(
    system_prompt,
    user_prompt,
    *,
    temperature=0.4,
    model=None,
    json_mode=False,
):
    kwargs = {
        "model": model or HINT_MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "timeout": AI_API_TIMEOUT_SECONDS,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    start = time.perf_counter()
    response = client.chat.completions.create(**kwargs)
    elapsed = time.perf_counter() - start
    text = (response.choices[0].message.content or "").strip()
    return text, elapsed


def limit_words(text, max_words=200):
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


def normalize_token(value):
    return re.sub(r"[^a-z]", "", value.lower())


def simple_stem(word):
    base = normalize_token(word)
    suffixes = ["ation", "ment", "ness", "ingly", "ing", "ed", "ly", "es", "s", "er"]
    for suffix in suffixes:
        if base.endswith(suffix) and len(base) - len(suffix) >= 3:
            return base[: -len(suffix)]
    return base


def is_hint_too_close_to_board(hint, board_words):
    normalized_hint = normalize_token(hint)
    stemmed_hint = simple_stem(hint)
    for word in board_words:
        normalized_word = normalize_token(word)
        stemmed_word = simple_stem(word)
        if normalized_hint == normalized_word:
            return True
        if stemmed_hint and stemmed_word and stemmed_hint == stemmed_word:
            return True
        shorter, longer = sorted(
            (normalized_hint, normalized_word), key=len
        )
        # Reject spelling tricks that contain a board word as their root/prefix.
        # Three-letter cards need a bounded check as well (for example, Pen ->
        # Pencel/Pencil); the previous four-letter minimum let these pass.
        prefix_extension_limit = 3 if len(shorter) == 3 else None
        if len(shorter) >= 4 and longer.startswith(shorter):
            return True
        if (
            prefix_extension_limit is not None
            and longer.startswith(shorter)
            and len(longer) - len(shorter) <= prefix_extension_limit
        ):
            return True
    return False


def remaining_target_count(target_words, history):
    found_targets = {
        guess
        for item in history
        for guess in item.get("correct_guesses", [])
    }
    return max(1, min(MAX_HINT_NUMBER, len(target_words) - len(found_targets)))


def format_interaction_history(history):
    if not history:
        return "No previous interactions in this round."

    lines = []
    for index, item in enumerate(history, start=1):
        guesses = ", ".join(item.get("guesses", [])) or "none"
        correct_guesses = ", ".join(item.get("correct_guesses", [])) or "none"
        if item.get("bomb_hit"):
            outcome = "BOMB HIT"
        elif item.get("timed_out") or item.get("outcome") == "timeout":
            outcome = "timed out"
        elif item.get("outcome") == "skip" or item.get("skipped"):
            outcome = f"skipped by {item.get('skipped_by') or item.get('guesser') or 'guesser'}"
        elif item.get("correct"):
            outcome = "at least one target correct"
        else:
            outcome = "no targets found"
        lines.append(
            f"Turn {index} | clue_giver={item.get('clue_giver', '')} | guesser={item.get('guesser', '')} | "
            f"clue=\"{item.get('hint', '')}\" N={item.get('hint_number', '')} | "
            f"intended=[{', '.join(item.get('intended_targets', [])) or 'none'}] | "
            f"expected_guesses=[{', '.join(item.get('expected_guesses', [])) or 'none'}] | "
            f"skip_interpretation=[{', '.join(item.get('skip_interpreted_cards', [])) or 'none'}] | "
            f"wrong_guess_replacements=[{', '.join(item.get('wrong_guess_replacements', [])) or 'none'}] | "
            f"guessed=[{guesses}] | correct=[{correct_guesses}] | outcome={outcome}"
        )
    return "\n".join(lines)


def format_baseline_history(history):
    """Game facts only: no intentions, expected guesses, rationales, or reflections."""
    if not history:
        return "No previous interactions in this round."
    lines = []
    for index, item in enumerate(history, start=1):
        guesses = ", ".join(item.get("guesses", [])) or "none"
        correct = ", ".join(item.get("correct_guesses", [])) or "none"
        incorrect = ", ".join(item.get("incorrect_guesses", [])) or "none"
        if item.get("bomb_hit"):
            outcome = "BOMB HIT"
        elif item.get("timed_out") or item.get("outcome") == "timeout":
            outcome = "timed out"
        elif item.get("outcome") == "skip" or item.get("skipped"):
            outcome = "skipped"
        elif item.get("correct"):
            outcome = "at least one target correct"
        else:
            outcome = "no targets found"
        lines.append(
            f"Turn {index} | clue=\"{item.get('hint', '')}\" N={item.get('hint_number', '')} | "
            f"guessed=[{guesses}] | correct=[{correct}] | incorrect=[{incorrect}] | outcome={outcome}"
        )
    return "\n".join(lines)


def format_baseline_round_memory(round_summaries):
    if not round_summaries:
        return "No previous rounds yet."
    lines = []
    for summary in round_summaries:
        lines.append(
            f"Round {summary.get('round', '')}: success={summary.get('success', '')}; "
            f"bomb_hit={summary.get('bomb_hit', '')}; medal={summary.get('medal', '')}"
        )
        lines.append(format_baseline_history(summary.get("interactions", [])))
    return "\n".join(lines)


def format_word_type_per_card(words, word_type_per_card):
    if not word_type_per_card:
        return "Not provided."
    missing = [word for word in words if not word_type_per_card.get(word)]
    if missing:
        return f"Missing word_type for: {', '.join(missing)}"
    return ", ".join(
        f"{word}: {word_type_per_card[word]}" for word in words
    )


def format_participant_feedback(history):
    feedback_lines = []
    for item in history:
        clue_giver = item.get("clue_giver", "")
        if clue_giver == "human":
            if not item.get("human_explanation_is_valid"):
                continue
            rating = item.get("human_understanding_rating")
            relationship_type = item.get("human_relationship_type", "")
            explanation = str(item.get("human_explanation_sanitized", "") or "").strip()
            if not rating and not relationship_type and not explanation:
                continue
        elif clue_giver == "ai":
            rating = item.get("human_understanding_rating")
            if not rating:
                continue
            relationship_type = ""
            explanation = ""
        else:
            continue

        line_parts = [
            f"- Perceived understanding: {rating}/5" if rating else "- Perceived understanding: not provided",
            f"  Relationship type: {relationship_type or 'not provided'}",
        ]
        if explanation:
            line_parts.append(f'  Explanation: "{explanation}"')
        feedback_lines.append("\n".join(line_parts))

    if not feedback_lines:
        return "No valid participant feedback yet."
    return "\n".join(feedback_lines)


def format_round_participant_feedback(round_summaries):
    feedback_lines = []
    for summary in round_summaries or []:
        round_number = summary.get("round", "")
        for item in summary.get("interactions", []):
            clue_giver = item.get("clue_giver", "")
            if clue_giver == "human":
                if not item.get("human_explanation_is_valid"):
                    continue
                rating = item.get("human_understanding_rating")
                relationship_type = item.get("human_relationship_type", "")
                explanation = str(item.get("human_explanation_sanitized", "") or "").strip()
                if not rating and not relationship_type and not explanation:
                    continue
            elif clue_giver == "ai":
                rating = item.get("human_understanding_rating")
                if not rating:
                    continue
                relationship_type = ""
                explanation = ""
            else:
                continue
            parts = [
                f"- Round {round_number}, turn {item.get('turn', '')}",
                f"  Perceived understanding: {rating}/5" if rating else "  Perceived understanding: not provided",
                f"  Relationship type: {relationship_type or 'not provided'}",
            ]
            if explanation:
                parts.append(f'  Explanation: "{explanation}"')
            feedback_lines.append("\n".join(parts))
    return "\n".join(feedback_lines)


def format_all_participant_feedback(history, round_summaries):
    chunks = [
        format_round_participant_feedback(round_summaries),
        format_participant_feedback(history),
    ]
    text = "\n".join(chunk for chunk in chunks if chunk and "No valid" not in chunk)
    return text or "No valid participant feedback yet."


def format_round_memory(round_summaries):
    if not round_summaries:
        return "No previous rounds yet."

    lines = []
    for summary in round_summaries:
        compact = {
            "round": summary.get("round"),
            "role": summary.get("role"),
            "word_type": summary.get("word_type"),
            "medal": summary.get("medal"),
            "success": summary.get("success"),
            "bomb_hit": summary.get("bomb_hit"),
            "turns": summary.get("turns"),
            "targets": summary.get("targets", []),
            "bombs": summary.get("bombs", summary.get("bomb")),
            "found_targets": summary.get("found_targets", []),
            "skips": summary.get("skips", 0),
            "ai_reflection": summary.get("ai_reflection", ""),
            "human_feedback": summary.get("human_feedback", ""),
            "interactions": [
                {
                    "turn": item.get("turn"),
                    "clue_giver": item.get("clue_giver"),
                    "guesser": item.get("guesser"),
                    "hint": item.get("hint"),
                    "hint_number": item.get("hint_number"),
                    "intended_targets": item.get("intended_targets", []),
                    "expected_guesses": item.get("expected_guesses", []),
                    "guesses": item.get("guesses", []),
                    "guess_order": item.get("guess_order", []),
                    "correct_guesses": item.get("correct_guesses", []),
                    "neutral_guesses": item.get("neutral_guesses", []),
                    "bomb_guess": item.get("bomb_guess"),
                    "outcome": item.get("outcome"),
                    "skipped": item.get("skipped", False),
                    "skip_interpreted_cards": item.get(
                        "skip_interpreted_cards", []
                    ),
                    "wrong_guess_replacements": item.get(
                        "wrong_guess_replacements", []
                    ),
                }
                for item in summary.get("interactions", [])
            ],
        }
        lines.append(json.dumps(compact, ensure_ascii=False))
    return "\n".join(lines)


def _memory_interaction_lines(interactions, round_label="current"):
    lines = []
    for item in interactions or []:
        clue_giver = item.get("clue_giver", "")
        guesser = item.get("guesser", "")
        hint = item.get("hint", "")
        hint_number = item.get("hint_number", "")
        intended = ", ".join(item.get("intended_targets", [])) or "none"
        expected = ", ".join(item.get("expected_guesses", [])) or "none"
        guesses = ", ".join(item.get("guesses", [])) or "none"
        guess_order = item.get("guess_order") or [
            {"position": position, "word": guess}
            for position, guess in enumerate(item.get("guesses", []), start=1)
        ]
        guess_order_text = ", ".join(
            f"{entry.get('position')}:{entry.get('word')}" for entry in guess_order
        ) or "none"
        correct = ", ".join(item.get("correct_guesses", [])) or "none"
        neutral = ", ".join(item.get("neutral_guesses", [])) or "none"
        skip_interpretation = (
            ", ".join(item.get("skip_interpreted_cards", [])) or "none"
        )
        wrong_replacements = (
            ", ".join(item.get("wrong_guess_replacements", [])) or "none"
        )
        rationale = str(item.get("guess_rationale", "") or "").strip()
        human_rating = item.get("human_understanding_rating")
        human_relationship = str(item.get("human_relationship_type", "") or "").strip()
        human_explanation = str(
            item.get("human_explanation_sanitized", "")
            or item.get("human_explanation_raw", "")
            or ""
        ).strip()
        ai_explanation = str(
            item.get("ai_explanation_sanitized", "")
            or item.get("ai_explanation", "")
            or ""
        ).strip()

        parts = [
            f"- {round_label} turn {item.get('turn', '')}: {clue_giver} clue -> {guesser} guesser",
            f"  clue=\"{hint}\" N={hint_number}; intended=[{intended}]; clue-giver expected guesses=[{expected}]",
            f"  actual guesses=[{guesses}]; guess_order=[{guess_order_text}]; correct=[{correct}]; neutral=[{neutral}]; outcome={item.get('outcome', '')}",
        ]
        if rationale:
            parts.append(f'  guesser rationale: "{rationale}"')
        if item.get("skipped") or item.get("outcome") in {"skip", "partial_skip"}:
            parts.append(
                f"  guesser's likely intended cards at skip=[{skip_interpretation}]"
            )
        if item.get("wrong_guess_replacements"):
            parts.append(
                f"  guesser would replace wrong choices with=[{wrong_replacements}]"
            )
        if human_rating:
            parts.append(f"  human understanding rating: {human_rating}/5")
        if human_relationship or human_explanation:
            parts.append(
                f"  human-described clue relationship: {human_relationship or 'not specified'}"
                + (f' - "{human_explanation}"' if human_explanation else "")
            )
        if ai_explanation:
            parts.append(f'  AI clue explanation shown to human: "{ai_explanation}"')
        lines.append("\n".join(parts))
    return lines


def format_persistent_teammate_memory(history, round_summaries):
    lines = [
        "Treat this as your working memory for the whole game. The API call is stateless, so do not assume you remember anything except what is written here.",
        "Use this memory to model the human teammate's associations, intended meanings, expected guesses, rationales, and feedback from the start of the game.",
    ]

    for summary in round_summaries or []:
        round_label = f"round {summary.get('round', '')}"
        lines.append(
            f"{round_label} summary: role={summary.get('role', '')}; medal={summary.get('medal', '')}; "
            f"success={summary.get('success', '')}; bomb_hit={summary.get('bomb_hit', '')}; "
            f"found_targets=[{', '.join(summary.get('found_targets', [])) or 'none'}]"
        )
        lines.extend(_memory_interaction_lines(summary.get("interactions", []), round_label))
        ai_reflection = str(summary.get("ai_reflection", "") or "").strip()
        human_feedback = str(summary.get("human_feedback", "") or "").strip()
        if ai_reflection:
            lines.append(f'{round_label} AI end-of-round reflection: "{ai_reflection}"')
        if human_feedback:
            lines.append(f'{round_label} human end-of-round feedback: "{human_feedback}"')

    if history:
        lines.append("Current round memory so far:")
        lines.extend(_memory_interaction_lines(history, "current round"))
    elif not round_summaries:
        lines.append("No prior turns yet. Build the teammate model as soon as evidence appears.")

    return "\n".join(lines)


def previous_hints(history):
    return [
        item.get("hint", "").strip().lower()
        for item in history
        if item.get("hint")
    ]


HINT_SYSTEM_PROMPT = """You are an expert clue-giver in a cooperative Codenames-style word game. You are partnered with one human teammate. Your shared goal is to find all target words quickly without picking either bomb.

GAME RULES
- The board has 16 cards. Hidden roles: 5 targets (good), 2 bombs (round-ending), 9 neutrals (safe but wrong).
- You output one English clue word and a number N. Your teammate then guesses N words from the board.
- The clue word must NOT appear on the board and must NOT be a morphological variant (no plural / verb-form / spelling trick).
- A great clue links 2 or 3 targets through one vivid, everyday association that any literate adult would recognize instantly.

HOW TO PICK A GREAT CLUE (think like a thoughtful human teammate)
1. Scan the remaining targets and group them into candidate clusters. Look for shared categories (animals, sports, kitchen), idioms ("breaking the ice"), famous pairings ("salt and pepper"), sensory imagery, or cultural archetypes.
2. For each candidate clue, mentally test it against EVERY neutral and BOTH BOMBS.
   - If the clue could reasonably point at a neutral, the teammate will probably pick that neutral. Lower N or pick a safer clue.
   - If the clue has ANY plausible link to either bomb, throw it away.
3. Prefer concrete, common, mainstream associations over clever or obscure ones. Your teammate is human and short on time.
4. Aim for the largest safe cluster. But a confident N=2 always beats a shaky N=4.
5. Avoid being a simple synonym of a single target. Reach for a richer concept that bridges multiple targets.
6. Use the round history. If a previous clue confused the teammate, do not reuse the same association style; switch angle. If a clue worked well, build on what they understood.
7. Never use the same clue word twice in a round.

PERSISTENT TEAMMATE MEMORY
- You are called through a stateless API. You only remember what is included in the prompt, so actively use the provided persistent teammate memory every turn.
- Build a mental model of the human from the whole game: what they intended, what they expected you to guess, what they actually guessed, and how they explained their reasoning.
- Adapt future clues and guesses to that model, as a careful human teammate would.

OUTPUT FORMAT — strict JSON only, no markdown, no commentary outside the JSON. Schema:
{
  "reasoning": "<one or two short sentences: which targets you chose, what the link is, and why the bombs and neutrals are not at risk>",
  "clue": "<one lowercase English word, letters only; a hyphen is allowed only in idiomatic compounds>",
  "number": <integer between 1 and 5>,
  "targets": ["<exact remaining target word as spelled in the input>", "..."],
  "expected_guesses": ["<exact available board word you expect the human to pick>", "..."]
}

CONSTRAINTS
- Return exactly "number" intended targets in "targets". Do not return fewer or more items.
- Return exactly "number" expected guesses in "expected_guesses". Do not return fewer or more items.
- Do not return duplicates in either "targets" or "expected_guesses".
- Every item in "targets" must be an exact remaining target word listed in the user message.
- Every item in "expected_guesses" must be an exact currently available board word listed in the user message. Do not return unavailable or unknown board words.
- Include the cards you realistically expect the human guesser to choose, even if one could be neutral or a bomb risk.
- "clue" must not appear on the board nor be a morphological variant.
- "reasoning" is logged for research analysis and is NEVER shown to the player during gameplay.
"""

BASELINE_HINT_SYSTEM_PROMPT = HINT_SYSTEM_PROMPT.replace(
    "PERSISTENT TEAMMATE MEMORY\n"
    "- You are called through a stateless API. You only remember what is included in the prompt, so actively use the provided persistent teammate memory every turn.\n"
    "- Build a mental model of the human from the whole game: what they intended, what they expected you to guess, what they actually guessed, and how they explained their reasoning.\n"
    "- Adapt future clues and guesses to that model, as a careful human teammate would.\n\n",
    "",
)


def build_hint_user_prompt(
    target_words,
    bomb_words,
    neutral_words,
    word_type,
    history,
    round_summaries=None,
    used_hints=None,
    forbidden_hint=None,
    condition=DEFAULT_CONDITION,
    repair_context=None,
):
    if isinstance(bomb_words, str) or bomb_words is None:
        bomb_words = [bomb_words] if bomb_words else []
    found_targets = {
        guess
        for item in history
        for guess in item.get("correct_guesses", [])
    }
    remaining_targets = [word for word in target_words if word not in found_targets]
    all_used = sorted(set(previous_hints(history) + (used_hints or [])))
    if forbidden_hint:
        all_used = sorted(set(all_used + [forbidden_hint.lower()]))

    forbidden_block = ", ".join(all_used) if all_used else "(none)"
    word_type_per_card = st.session_state.get("word_type_per_card", {})
    board_words = target_words + neutral_words + list(bomb_words)
    already_guessed = {
        guess
        for item in history
        for guess in item.get("guesses", [])
    }
    available_board = [word for word in board_words if word not in already_guessed]
    feedback_block = ""
    if condition == "adaptive":
        feedback_block = (
            "\n\nPrevious participant feedback:\n"
            f"{format_all_participant_feedback(history, round_summaries or [])}"
        )
    interaction_memory = (
        format_interaction_history(history)
        if condition == "adaptive"
        else format_baseline_history(history)
    )
    round_memory = (
        format_round_memory(round_summaries or [])
        if condition == "adaptive"
        else format_baseline_round_memory(round_summaries or [])
    )
    teammate_memory = (
        "\n\nPersistent teammate memory from the whole game:\n"
        f"{format_persistent_teammate_memory(history, round_summaries or [])}"
        if condition == "adaptive"
        else ""
    )
    repair_block = ""
    if repair_context:
        repair_targets = repair_context.get("unresolved_targets", [])
        repair_block = (
            "\n\nMANDATORY SKIP REPAIR:\n"
            f"Turn {repair_context.get('skipped_turn')} was skipped. Generate a NEW clue for exactly "
            f"these same unresolved targets: {', '.join(repair_targets)}.\n"
            f"Do not repeat the skipped clue \"{repair_context.get('skipped_hint', '')}\". "
            "Do not replace, add, or drop targets. Set number to the target count and return exactly "
            "this target set in targets.\n"
        )
        if condition == "adaptive":
            interpretation = repair_context.get("participant_interpretation", [])
            reasoning = str(repair_context.get("participant_reasoning", "") or "").strip()
            reflection = str(repair_context.get("participant_reflection", "") or "").strip()
            repair_block += (
                "Participant context from the skipped interaction (use it to change the communicative angle):\n"
                f"- interpreted cards: {', '.join(interpretation) or '(none)'}\n"
                f"- guess reasoning: {reasoning or '(none)'}\n"
                f"- reflection: {reflection or '(none)'}\n"
            )

    return (
        f"Word type for this round: {word_type}\n"
        f"Word type per card: {format_word_type_per_card(board_words, word_type_per_card)}\n"
        f"Remaining target words (you must aim only at these): {', '.join(remaining_targets) or '(none)'}\n"
        f"Targets already found this round: {', '.join(found_targets) or '(none)'}\n"
        f"Available board words the human can still choose from: {', '.join(available_board)}\n"
        f"Neutral words (AVOID — your clue must not fit these): {', '.join(neutral_words)}\n"
        f"BOMB words (NEVER let your clue fit these): {', '.join(bomb_words)}\n\n"
        f"Forbidden clue words (already used this round, do not repeat): {forbidden_block}\n\n"
        "Interaction history so far this round (use it to learn what your teammate understood and what they missed):\n"
        f"{interaction_memory}\n\n"
        "Memory from previous rounds in this game:\n"
        f"{round_memory}"
        f"{teammate_memory}\n\n"
        f"{feedback_block}\n\n"
        f"{repair_block}\n\n"
        "Produce the best one-word clue you can, then explain (in the reasoning field) the link and why each neutral and both bombs are safe. Respond with the JSON object only."
    )


def parse_hint_json(raw_text, remaining_targets, available_board=None):
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return "", 0, [], [], ""

    if not isinstance(data, dict):
        return "", 0, [], [], ""

    clue_raw = str(data.get("clue", "") or "").strip().lower()
    clue = clue_raw if re.fullmatch(r"[a-z]+(-[a-z]+)*", clue_raw) else ""

    raw_number = data.get("number")
    if (
        not isinstance(raw_number, int)
        or isinstance(raw_number, bool)
        or raw_number <= 0
        or raw_number > MAX_HINT_NUMBER
    ):
        return "", 0, [], [], ""
    hint_number = raw_number

    raw_targets = data.get("targets")
    raw_expected_guesses = data.get("expected_guesses")
    if not isinstance(raw_targets, list) or not isinstance(raw_expected_guesses, list):
        return "", 0, [], [], ""
    if len(raw_targets) != hint_number or len(raw_expected_guesses) != hint_number:
        return "", 0, [], [], ""
    if not all(isinstance(value, str) for value in raw_targets + raw_expected_guesses):
        return "", 0, [], [], ""
    if len(set(raw_targets)) != hint_number or len(set(raw_expected_guesses)) != hint_number:
        return "", 0, [], [], ""
    if any(value not in remaining_targets for value in raw_targets):
        return "", 0, [], [], ""
    available_board = available_board or []
    if any(value not in available_board for value in raw_expected_guesses):
        return "", 0, [], [], ""

    intended_targets = list(raw_targets)
    expected_guesses = list(raw_expected_guesses)

    explanation = str(data.get("reasoning", "") or "").strip()
    explanation = limit_words(explanation, 60)

    return clue, hint_number, intended_targets, expected_guesses, explanation


AI_TURN_EXPLANATION_SYSTEM_PROMPT = """You explain your own clue in a cooperative word association game after the human has already guessed.

Write a short, general explanation of the relationship behind the clue.
Do not mention any exact card words from the board. Do not mention target words.
Explain only the general relationship or concept behind the clue.
Return strict JSON only:
{
  "relationship_type": "Category / shared type" | "Theme / shared situation" | "Function / use or purpose" | "Other",
  "explanation": "<one sentence, max 25 words, no card names>"
}
"""


SAFE_AI_EXPLANATION_FALLBACK = (
    "The clue was based on a general semantic association between the intended concepts."
)


def _empty_ai_explanation_result(relationship_type="Other", raw="", reason="generation_failed"):
    return {
        "ai_relationship_type": relationship_type or "Other",
        "ai_explanation_raw": raw or "",
        "ai_explanation_sanitized": SAFE_AI_EXPLANATION_FALLBACK,
        "ai_explanation": SAFE_AI_EXPLANATION_FALLBACK,
        "ai_explanation_is_valid": False,
        "ai_explanation_blocked_reason": reason,
    }


def generate_ai_turn_explanation(
    clue,
    hint_number,
    intended_targets,
    guesses,
    board_words,
    existing_reasoning="",
):
    base_user_prompt = (
        f"Clue: {clue}\n"
        f"Number: {hint_number}\n"
        f"Intended cards: {', '.join(intended_targets)}\n"
        f"Human guesses: {', '.join(guesses) or '(none)'}\n"
        f"Forbidden exact board/card words: {', '.join(board_words or [])}\n"
        f"Your hidden reasoning from clue generation: {existing_reasoning}\n\n"
        "Explain the general relationship behind the clue without naming any board cards. "
        "Do not mention any exact card words from the board. Do not mention target words."
    )
    strict_suffix = (
        "\n\nPrevious explanation was invalid because it named a board/card word. "
        "Regenerate once. Use only abstract/general concepts, categories, or relationships. "
        "Do not include any visible board word, target word, neutral word, bomb word, or simple plural/singular variant."
    )

    last_raw_explanation = ""
    last_relationship_type = "Other"
    for attempt in range(2):
        try:
            raw, _ = call_openai_chat(
                AI_TURN_EXPLANATION_SYSTEM_PROMPT,
                base_user_prompt + (strict_suffix if attempt else ""),
                temperature=0.2 if attempt == 0 else 0.0,
                model=REFLECTION_MODEL_NAME,
                json_mode=True,
            )
            data = json.loads(raw)
            relationship_type = str(data.get("relationship_type", "") or "").strip()
            if relationship_type not in {
                "Category / shared type",
                "Theme / shared situation",
                "Function / use or purpose",
                "Other",
            }:
                relationship_type = "Other"
            explanation = limit_words(str(data.get("explanation", "") or "").strip(), 25)
            last_raw_explanation = explanation
            last_relationship_type = relationship_type
            if not explanation:
                continue
            if mentions_board_word(explanation, board_words):
                continue
            return {
                "ai_relationship_type": relationship_type,
                "ai_explanation_raw": explanation,
                "ai_explanation_sanitized": explanation,
                "ai_explanation": explanation,
                "ai_explanation_is_valid": True,
                "ai_explanation_blocked_reason": "",
            }
        except Exception:
            continue

    reason = "board_word" if last_raw_explanation else "generation_failed"
    return _empty_ai_explanation_result(last_relationship_type, last_raw_explanation, reason)


def _empty_ai_call_meta():
    return {"raw_response": "", "response_time_sec": 0.0, "attempts": 0}


def _generate_hint_with_forbidden(
    target_words,
    bomb_words,
    neutral_words,
    word_type,
    history,
    used_hints,
    round_summaries,
    forbidden_hint=None,
    condition=DEFAULT_CONDITION,
    repair_context=None,
):
    if isinstance(bomb_words, str) or bomb_words is None:
        bomb_words = [bomb_words] if bomb_words else []
    used_hint_set = set(previous_hints(history) + (used_hints or []))
    if forbidden_hint:
        used_hint_set.add(forbidden_hint.lower())
    board_words = target_words + neutral_words + list(bomb_words)
    found_targets = {
        guess
        for item in history
        for guess in item.get("correct_guesses", [])
    }
    remaining_targets = [word for word in target_words if word not in found_targets]
    required_targets = list((repair_context or {}).get("unresolved_targets", []))
    already_guessed = {
        guess
        for item in history
        for guess in item.get("guesses", [])
    }
    available_board = [word for word in board_words if word not in already_guessed]

    last_raw = ""
    total_time = 0.0
    attempts = 0
    for _ in range(3):
        attempts += 1
        try:
            raw, elapsed = call_openai_chat(
                HINT_SYSTEM_PROMPT if condition == "adaptive" else BASELINE_HINT_SYSTEM_PROMPT,
                build_hint_user_prompt(
                    target_words,
                    bomb_words,
                    neutral_words,
                    word_type,
                    history,
                    round_summaries,
                    used_hints,
                    forbidden_hint,
                    condition,
                    repair_context,
                ),
                temperature=0.55,
                model=HINT_MODEL_NAME,
                json_mode=True,
            )
        except Exception as error:
            last_raw = f"<api_error: {error}>"
            total_time += 0.0
            continue

        last_raw = raw
        total_time += elapsed
        hint, hint_number, intended_targets, expected_guesses, explanation = parse_hint_json(
            raw, remaining_targets, available_board
        )
        if (
            hint
            and hint not in used_hint_set
            and not is_hint_too_close_to_board(hint, board_words)
            and intended_targets
            and (not required_targets or set(intended_targets) == set(required_targets))
            and (not required_targets or hint_number == len(required_targets))
        ):
            return {
                "hint": hint,
                "hint_number": hint_number,
                "intended_targets": intended_targets,
                "expected_guesses": expected_guesses,
                "explanation": explanation,
                "raw_response": last_raw,
                "response_time_sec": round(total_time, 3),
                "attempts": attempts,
            }

    raise AIClueGenerationError(
        "Failed to generate a valid AI clue after 3 attempts.",
        attempts=attempts,
        last_raw=last_raw,
        response_time_sec=round(total_time, 3),
    )


def generate_ai_hint(
    target_words,
    bomb_words,
    neutral_words,
    word_type,
    history=None,
    used_hints=None,
    round_summaries=None,
    condition=DEFAULT_CONDITION,
    repair_context=None,
):
    return _generate_hint_with_forbidden(
        target_words,
        bomb_words,
        neutral_words,
        word_type,
        history or [],
        used_hints or [],
        round_summaries or [],
        forbidden_hint=(repair_context or {}).get("skipped_hint"),
        condition=condition,
        repair_context=repair_context,
    )


def generate_ai_hint_reroll(
    target_words,
    bomb_words,
    neutral_words,
    word_type,
    previous_hint,
    history=None,
    used_hints=None,
    round_summaries=None,
    condition=DEFAULT_CONDITION,
):
    return _generate_hint_with_forbidden(
        target_words,
        bomb_words,
        neutral_words,
        word_type,
        history or [],
        used_hints or [],
        round_summaries or [],
        forbidden_hint=previous_hint,
        condition=condition,
        repair_context=None,
    )


GUESS_SYSTEM_PROMPT = """You are an expert semantic guesser in a cooperative Codenames-style word game. Your human teammate just gave you a clue word and a number N. Your job: pick exactly N words from the available board that a normal human would most likely mean.

GAME RULES
- The board has 16 words. Some are good targets, some are neutral (safe but wrong), two are bombs (round-ending).
- You only see the clue and the words — never the hidden roles.
- Hitting either bomb ends the round with zero points.

HOW TO PICK GREAT GUESSES
1. First translate the clue into its most ordinary meaning, including common non-English clues if obvious. For example, Persian "دزد دریایی" means pirate.
2. For EVERY available board word, mentally score the association from 0 to 5:
   - 5 = direct, iconic, or definitional link (pirate -> Ship, treasure -> Gold)
   - 4 = strong everyday category, setting, tool, role, or famous pairing
   - 3 = plausible but secondary link
   - 0-2 = weak, punny, obscure, spelling-based, or only connected by a forced story
3. Pick exactly N words with the highest scores. Order them strongest first.
4. Prefer direct object/setting/category links over abstract vibes. If the clue is "pirate", Ship beats Shoe, Crown, or Paper.
5. Never pick a word just because you can invent a clever explanation. If a normal human would not immediately understand the link, downgrade it.
6. If two words are close, pick the more concrete and mainstream association.
7. Use the round history. Avoid repeating any word that was already guessed; learn from what your teammate intended last time.

PERSISTENT TEAMMATE MEMORY
- You are called through a stateless API. You only remember what is included in the prompt, so actively use the provided persistent teammate memory every turn.
- Build a mental model of the human from the whole game: their intended targets, expected guesses, guess rationales, ratings, and explanations.
- Guess like a teammate who has been paying attention from the first turn, not like an isolated one-shot model.

WHEN TO REFUSE
- Output exactly REROLL_HINT only if the clue is genuinely meaningless or unrelated to every available board word. Last resort.
- Use action="skip" only if skipping is allowed AND no available word has at least a plausible score of 3. Last resort.
- If one or more guesses are strong but the remaining guesses would be unsafe, return action="partial_skip" with only the strong guesses. This consumes one full skip, but is better than risking a bomb.
- For action="skip", include up to N unselected cards in "interpreted_cards".
- For action="partial_skip", include only cards you have NOT already guessed, with at most N minus the number of completed guesses. These are the remaining cards you think the clue-giver most likely meant.

OUTPUT FORMAT — strict JSON only, no markdown, no commentary outside the JSON. Schema:
{
  "action": "guess", "partial_skip", or "skip",
  "reasoning": "<3 to 30 words explaining the direct link for each guess and, if useful, a close alternative you rejected; shown to the player and logged>",
  "guesses": ["<exact board word>", "..."],
  "interpreted_cards": ["<exact board word you think the clue was meant for>", "..."]
}

OR, instead of JSON, exactly this literal token on a single line:
REROLL_HINT
"""

BASELINE_GUESS_SYSTEM_PROMPT = GUESS_SYSTEM_PROMPT.replace(
    "PERSISTENT TEAMMATE MEMORY\n"
    "- You are called through a stateless API. You only remember what is included in the prompt, so actively use the provided persistent teammate memory every turn.\n"
    "- Build a mental model of the human from the whole game: their intended targets, expected guesses, guess rationales, ratings, and explanations.\n"
    "- Guess like a teammate who has been paying attention from the first turn, not like an isolated one-shot model.\n\n",
    "",
).replace(
    "shown to the player and logged",
    "logged for research and never shown to the player",
).replace(
    "learn from what your teammate intended last time",
    "learn only from which guesses were correct or incorrect last time",
)


def build_guess_user_prompt(
    board,
    hint,
    max_guesses,
    remaining_rerolls,
    history,
    previous_guesses,
    round_summaries,
    remaining_skips,
    can_skip,
    condition=DEFAULT_CONDITION,
):
    available_board = [word for word in board if word not in previous_guesses]
    word_type_per_card = st.session_state.get("word_type_per_card", {})
    feedback_block = ""
    if condition == "adaptive":
        feedback_block = (
            "\n\nPrevious participant feedback:\n"
            f"{format_all_participant_feedback(history, round_summaries or [])}"
        )
    interaction_memory = (
        format_interaction_history(history)
        if condition == "adaptive"
        else format_baseline_history(history)
    )
    round_memory = (
        format_round_memory(round_summaries or [])
        if condition == "adaptive"
        else format_baseline_round_memory(round_summaries or [])
    )
    teammate_memory = (
        "\n\nPersistent teammate memory from the whole game:\n"
        f"{format_persistent_teammate_memory(history, round_summaries or [])}"
        if condition == "adaptive"
        else ""
    )
    return (
        f"Available board words (only choose from these): {', '.join(available_board)}\n"
        f"Word type per available card: {format_word_type_per_card(available_board, word_type_per_card)}\n"
        f"Words already guessed this round (do NOT repeat): {', '.join(previous_guesses) or '(none)'}\n\n"
        f"Your teammate's clue: \"{hint}\"\n"
        f"Number of guesses to produce (N): {max_guesses}\n\n"
        "Before answering, internally rank every available board word by direct semantic association to the clue. "
        "Your final guesses must be the top N exact board words, not random filler.\n\n"
        f"Skipping allowed right now: {'yes' if can_skip else 'no'}\n"
        f"Remaining skips this round: {remaining_skips}\n"
        f"Remaining clue rerolls: {remaining_rerolls}\n\n"
        "You may make fewer than N strong guesses and set action=partial_skip when the remaining choices are dangerously uncertain. "
        "A partial skip preserves the guesses already made but consumes one full skip. Prefer it over a serious bomb risk.\n\n"
        "Interaction history so far this round:\n"
        f"{interaction_memory}\n\n"
        "Memory from previous rounds:\n"
        f"{round_memory}"
        f"{teammate_memory}\n\n"
        f"{feedback_block}\n\n"
        "Default to guessing. REROLL_HINT and action=skip are last resorts. "
        "Respond with the JSON object or the REROLL_HINT literal."
    )


def build_guess_repair_prompt(
    board,
    hint,
    max_guesses,
    previous_guesses,
    previous_response,
    history=None,
    round_summaries=None,
    condition=DEFAULT_CONDITION,
):
    available_board = [word for word in board if word not in previous_guesses]
    return (
        f"Available board words (choose only exact words from this list): {', '.join(available_board)}\n"
        f"Words already guessed and forbidden: {', '.join(previous_guesses) or '(none)'}\n"
        f"Clue: \"{hint}\"\n"
        f"N: {max_guesses}\n\n"
        "Your previous response was unusable or did not contain enough exact board words:\n"
        f"{previous_response}\n\n"
        + (
            "Persistent teammate memory from the whole game:\n"
            f"{format_persistent_teammate_memory(history or [], round_summaries or [])}\n\n"
            if condition == "adaptive"
            else ""
        )
        + "Return strict JSON only. Pick the top N exact board words by direct, everyday semantic association. "
        "Do not add unrelated filler. Schema: "
        '{"reasoning":"short reason, 3 to 30 words","guesses":["Exact board word"]}'
    )


def parse_guess_json(raw_text, available_board, max_guesses):
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return [], ""

    if not isinstance(data, dict):
        return [], ""

    raw_guesses = data.get("guesses", []) or []
    if not isinstance(raw_guesses, list):
        return [], ""

    board_lookup = {word.lower(): word for word in available_board}
    valid = []
    seen = set()
    for value in raw_guesses:
        key = str(value).strip().lower()
        if key in board_lookup and key not in seen:
            valid.append(board_lookup[key])
            seen.add(key)
        if len(valid) >= max_guesses:
            break
    rationale = limit_words(str(data.get("reasoning", "") or "").strip(), 30)
    return valid, rationale


def parse_guess_action(raw_text):
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return "guess"
    if not isinstance(data, dict):
        return "guess"
    action = str(data.get("action", "guess") or "guess").strip().lower()
    return action if action in {"guess", "partial_skip", "skip"} else "guess"


def parse_interpreted_cards(raw_text, available_board, max_cards):
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, dict):
        return []
    values = data.get("interpreted_cards", []) or []
    if not isinstance(values, list):
        return []
    board_lookup = {word.lower(): word for word in available_board}
    interpreted = []
    seen = set()
    for value in values:
        key = str(value).strip().lower()
        if key in board_lookup and key not in seen:
            interpreted.append(board_lookup[key])
            seen.add(key)
        if len(interpreted) >= max_cards:
            break
    return interpreted


WRONG_GUESS_REPLACEMENT_SYSTEM_PROMPT = """You are the AI guesser in a cooperative word-association game.
The result of your completed turn has now revealed that one or more of your selected cards were wrong neutral cards. No bomb was selected.

Choose exactly the requested number of different replacement cards that you would have selected instead, using only the available card labels provided. Do not choose any card already selected in that turn.

Return strict JSON only:
{"replacement_cards": ["<exact available card>", "..."]}
"""


def generate_ai_wrong_guess_replacements(
    board,
    previous_guesses,
    hint,
    wrong_guesses,
):
    replacement_count = len(wrong_guesses or [])
    available_cards = [
        word for word in board if word not in set(previous_guesses or [])
    ]
    meta = {
        "cards": [],
        "raw_response": "",
        "response_time_sec": 0.0,
        "attempts": 0,
    }
    if replacement_count <= 0 or not available_cards:
        return meta
    try:
        raw, elapsed = call_openai_chat(
            WRONG_GUESS_REPLACEMENT_SYSTEM_PROMPT,
            (
                f'Clue: "{hint}"\n'
                f"Wrong cards from your completed turn: {', '.join(wrong_guesses)}\n"
                f"Available replacement cards: {', '.join(available_cards)}\n"
                f"Number of replacement cards required: {replacement_count}\n"
            ),
            temperature=0.0,
            model=GUESS_MODEL_NAME,
            json_mode=True,
        )
        meta["raw_response"] = raw
        meta["response_time_sec"] = round(elapsed, 3)
        meta["attempts"] = 1
        data = json.loads(raw)
        values = data.get("replacement_cards", []) if isinstance(data, dict) else []
        lookup = {word.lower(): word for word in available_cards}
        cards = []
        seen = set()
        for value in values if isinstance(values, list) else []:
            key = str(value).strip().lower()
            if key in lookup and key not in seen:
                cards.append(lookup[key])
                seen.add(key)
            if len(cards) >= replacement_count:
                break
        meta["cards"] = cards if len(cards) == replacement_count else []
    except Exception as error:
        meta["raw_response"] = f"<replacement_error: {error}>"
        meta["attempts"] = max(1, meta["attempts"])
    return meta


def ai_guess(
    board,
    hint,
    max_guesses,
    remaining_rerolls,
    history=None,
    previous_guesses=None,
    round_summaries=None,
    remaining_skips=0,
    can_skip=False,
    condition=DEFAULT_CONDITION,
):
    history = history or []
    previous_guesses = previous_guesses or []
    available_board = [word for word in board if word not in previous_guesses]

    meta = _empty_ai_call_meta()
    raw = ""
    try:
        raw, elapsed = call_openai_chat(
            GUESS_SYSTEM_PROMPT if condition == "adaptive" else BASELINE_GUESS_SYSTEM_PROMPT,
            build_guess_user_prompt(
                board,
                hint,
                max_guesses,
                remaining_rerolls,
                history,
                previous_guesses,
                round_summaries,
                remaining_skips,
                can_skip,
                condition,
            ),
            temperature=0.2,
            model=GUESS_MODEL_NAME,
            json_mode=False,
        )
        meta["raw_response"] = raw
        meta["response_time_sec"] = round(elapsed, 3)
        meta["attempts"] = 1
    except Exception as error:
        meta["raw_response"] = f"<api_error: {error}>"
        meta["response_time_sec"] = 0.0
        meta["attempts"] = 1
        raw = ""

    if raw:
        upper = raw.strip().upper()
        if upper == "REROLL_HINT" and remaining_rerolls > 0:
            return {"action": "reroll", "guesses": [], "guess_rationale": "", **meta}
        if upper == "SKIP_CLUE" and can_skip and remaining_skips > 0:
            return {"action": "skip", "guesses": [], "guess_rationale": "", **meta}

        valid_guesses, guess_rationale = parse_guess_json(raw, available_board, max_guesses)
        interpreted_cards = parse_interpreted_cards(raw, available_board, max_guesses)
        requested_action = parse_guess_action(raw)
        if (
            requested_action == "skip"
            and can_skip
            and remaining_skips > 0
            and interpreted_cards
        ):
            return {
                "action": "skip",
                "guesses": [],
                "skip_interpreted_cards": interpreted_cards,
                "guess_rationale": guess_rationale,
                **meta,
            }
        partial_skip_is_valid = (
            requested_action == "partial_skip"
            and can_skip
            and remaining_skips > 0
            and 0 < len(valid_guesses) < min(max_guesses, len(available_board))
        )
        if not valid_guesses:
            tokens = [
                token.strip().lower()
                for token in re.split(r"[,\n]", raw)
                if token.strip()
            ]
            board_lookup = {word.lower(): word for word in available_board}
            seen = set()
            for token in tokens:
                if token in board_lookup and token not in seen:
                    valid_guesses.append(board_lookup[token])
                    seen.add(token)
                if len(valid_guesses) >= max_guesses:
                    break

        if (
            not partial_skip_is_valid
            and len(valid_guesses) < min(max_guesses, len(available_board))
        ):
            try:
                repair_raw, repair_elapsed = call_openai_chat(
                    GUESS_SYSTEM_PROMPT if condition == "adaptive" else BASELINE_GUESS_SYSTEM_PROMPT,
                    build_guess_repair_prompt(
                        board,
                        hint,
                        max_guesses,
                        previous_guesses,
                        raw,
                        history,
                        round_summaries,
                        condition,
                    ),
                    temperature=0.0,
                    model=GUESS_MODEL_NAME,
                    json_mode=True,
                )
                repaired_guesses, repair_rationale = parse_guess_json(
                    repair_raw, available_board, max_guesses
                )
                repaired_interpretation = parse_interpreted_cards(
                    repair_raw, available_board, max_guesses
                )
                meta["raw_response"] = f"{raw}\n\n<repair_response>\n{repair_raw}"
                meta["response_time_sec"] = round(
                    (meta["response_time_sec"] or 0.0) + repair_elapsed, 3
                )
                meta["attempts"] = 2
                if len(repaired_guesses) > len(valid_guesses):
                    valid_guesses = repaired_guesses
                    guess_rationale = repair_rationale or guess_rationale
                if len(repaired_interpretation) > len(interpreted_cards):
                    interpreted_cards = repaired_interpretation
            except Exception as error:
                meta["raw_response"] = (
                    f"{meta['raw_response']}\n\n<repair_error: {error}>"
                )

        required_guess_count = min(max_guesses, len(available_board))
        # Never silently record an undersized normal guess as though the AI
        # completed the requested N guesses. If both the original response and
        # its repair remain incomplete, preserve the usable guesses as an
        # explicit partial skip whenever the game rules allow one.
        if (
            valid_guesses
            and not partial_skip_is_valid
            and len(valid_guesses) < required_guess_count
            and can_skip
            and remaining_skips > 0
        ):
            partial_skip_is_valid = True
            meta["raw_response"] = (
                f"{meta['raw_response']}\n\n<normalized_action: partial_skip; "
                "incomplete normal guess after repair>"
            )

        if valid_guesses:
            if partial_skip_is_valid:
                selected = set(valid_guesses)
                remaining_slots = max(0, required_guess_count - len(valid_guesses))
                interpreted_cards = [
                    card for card in interpreted_cards if card not in selected
                ][:remaining_slots]
            if not guess_rationale:
                guess_rationale = (
                    f"I chose {', '.join(valid_guesses[:max_guesses])} because they seemed closest to the clue {hint}."
                )
            return {
                "action": (
                    "partial_skip"
                    if partial_skip_is_valid
                    else "guess"
                ),
                "guesses": valid_guesses[:max_guesses],
                "skip_interpreted_cards": (
                    interpreted_cards if partial_skip_is_valid else []
                ),
                "guess_rationale": guess_rationale,
                **meta,
            }

    if can_skip and remaining_skips > 0:
        return {"action": "skip", "guesses": [], "guess_rationale": "", **meta}
    if remaining_rerolls > 0:
        return {"action": "reroll", "guesses": [], "guess_rationale": "", **meta}
    return {"action": "guess", "guesses": [], "guess_rationale": "", **meta}


REFLECTION_SYSTEM_PROMPT = """You are an AI teammate writing a short reflection at the end of one round of a cooperative word game. Your reader is the human player.

Your reflection should:
1. If you gave the clues, explain plainly why each clue was meant for which targets, what link you used (category, metaphor, idiom, image), and how you tried to keep the bombs and neutrals safe. Acknowledge any guess that went wrong.
2. If the human gave the clues, compare their marked intended targets to your guesses. Where you misread, say what association pulled you the wrong way. Where you guessed right, say what clicked.
3. Mention any skips and what made the clue feel risky.
4. End with one specific, actionable suggestion the team can apply in the next round.
5. Be warm, plain, and concrete. No empty praise. Maximum 180 words.
"""


def generate_ai_round_reflection(
    target_words,
    bomb_words,
    neutral_words,
    word_type,
    role,
    history,
    round_success,
    round_bomb_hit,
    round_medal,
    condition=DEFAULT_CONDITION,
):
    if isinstance(bomb_words, str) or bomb_words is None:
        bomb_words = [bomb_words] if bomb_words else []
    user_prompt = (
        f"Round role: {role}\n"
        f"Word type: {word_type}\n"
        f"Targets: {', '.join(target_words)}\n"
        f"Neutral words: {', '.join(neutral_words)}\n"
        f"Bombs: {', '.join(bomb_words)}\n"
        f"All targets found: {round_success}\n"
        f"Bomb hit: {round_bomb_hit}\n"
        f"Medal: {round_medal}\n\n"
        "Interaction history:\n"
        f"{format_interaction_history(history) if condition == 'adaptive' else format_baseline_history(history)}\n"
    )
    try:
        text, _ = call_openai_chat(
            REFLECTION_SYSTEM_PROMPT,
            user_prompt,
            temperature=0.4,
            model=REFLECTION_MODEL_NAME,
            json_mode=False,
        )
        return limit_words(text, 200)
    except Exception:
        return (
            "I could not generate a reflection this time. Look back at the history above: "
            "compare each clue with its intended targets and the actual guesses, and note "
            "what association should be clearer in the next round."
        )


def validate_human_hint(hint, board_words):
    cleaned = hint.strip().lower()
    if not cleaned:
        return False, "Please enter a clue word."
    if not re.fullmatch(r"[a-z-]+", cleaned):
        return False, "The clue must be exactly one word."
    if is_hint_too_close_to_board(cleaned, board_words):
        return False, "This clue is too close to a board word. Please choose a different word."
    return True, ""


def validate_human_hint_with_history(hint, board_words, history, used_hints=None):
    is_valid, message = validate_human_hint(hint, board_words)
    if not is_valid:
        return is_valid, message

    cleaned = hint.strip().lower()
    if cleaned in set(previous_hints(history) + (used_hints or [])):
        return False, "You already used this clue. Please choose a new one-word clue."
    return True, ""
