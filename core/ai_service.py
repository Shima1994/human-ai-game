import json
import random
import re
import time

import streamlit as st
from openai import OpenAI

from core.constants import (
    GUESS_MODEL_NAME,
    HINT_MODEL_NAME,
    MAX_HINT_NUMBER,
    REFLECTION_MODEL_NAME,
    TARGET_COUNT,
)
from core.validation import mentions_board_word

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

FALLBACK_HINTS = [
    "signal",
    "pattern",
    "linkage",
    "shared",
    "thread",
    "aspect",
    "angle",
    "bridge",
    "field",
    "motion",
    "shape",
    "anchor",
    "path",
    "zone",
    "core",
    "trace",
    "frame",
    "bond",
    "spark",
    "source",
    "guide",
    "match",
    "route",
    "sense",
    "theme",
    "point",
    "circle",
    "focus",
    "origin",
    "logic",
    "union",
    "vector",
]


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
        if len(normalized_hint) >= 4 and len(normalized_word) >= 4:
            if normalized_hint.startswith(normalized_word) or normalized_word.startswith(
                normalized_hint
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
            f"guessed=[{guesses}] | correct=[{correct_guesses}] | outcome={outcome}"
        )
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
                    "guesses": item.get("guesses", []),
                    "correct_guesses": item.get("correct_guesses", []),
                    "neutral_guesses": item.get("neutral_guesses", []),
                    "bomb_guess": item.get("bomb_guess"),
                    "outcome": item.get("outcome"),
                    "skipped": item.get("skipped", False),
                }
                for item in summary.get("interactions", [])
            ],
        }
        lines.append(json.dumps(compact, ensure_ascii=False))
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

OUTPUT FORMAT — strict JSON only, no markdown, no commentary outside the JSON. Schema:
{
  "reasoning": "<one or two short sentences: which targets you chose, what the link is, and why the bombs and neutrals are not at risk>",
  "clue": "<one lowercase English word, letters only; a hyphen is allowed only in idiomatic compounds>",
  "number": <integer between 1 and 5>,
  "targets": ["<exact remaining target word as spelled in the input>", "..."]
}

CONSTRAINTS
- "number" must equal the length of "targets".
- "targets" must be a subset of the remaining target words listed in the user message.
- "clue" must not appear on the board nor be a morphological variant.
- "reasoning" is logged for research analysis and is NEVER shown to the player during gameplay.
"""


def build_hint_user_prompt(
    target_words,
    bomb_words,
    neutral_words,
    word_type,
    history,
    round_summaries=None,
    used_hints=None,
    forbidden_hint=None,
    condition="baseline",
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
    feedback_block = ""
    if condition == "adaptive":
        feedback_block = (
            "\n\nPrevious participant feedback:\n"
            f"{format_all_participant_feedback(history, round_summaries or [])}"
        )

    return (
        f"Word type for this round: {word_type}\n"
        f"Word type per card: {format_word_type_per_card(board_words, word_type_per_card)}\n"
        f"Remaining target words (you must aim only at these): {', '.join(remaining_targets) or '(none)'}\n"
        f"Targets already found this round: {', '.join(found_targets) or '(none)'}\n"
        f"Neutral words (AVOID — your clue must not fit these): {', '.join(neutral_words)}\n"
        f"BOMB words (NEVER let your clue fit these): {', '.join(bomb_words)}\n\n"
        f"Forbidden clue words (already used this round, do not repeat): {forbidden_block}\n\n"
        "Interaction history so far this round (use it to learn what your teammate understood and what they missed):\n"
        f"{format_interaction_history(history)}\n\n"
        "Memory from previous rounds in this game:\n"
        f"{format_round_memory(round_summaries or [])}\n\n"
        f"{feedback_block}\n\n"
        "Produce the best one-word clue you can, then explain (in the reasoning field) the link and why each neutral and both bombs are safe. Respond with the JSON object only."
    )


def parse_hint_json(raw_text, fallback_n, remaining_targets):
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return "", fallback_n, [], ""

    if not isinstance(data, dict):
        return "", fallback_n, [], ""

    clue_raw = str(data.get("clue", "") or "").strip().lower()
    clue = re.sub(r"[^a-z-]", "", clue_raw)
    if clue and not re.fullmatch(r"[a-z]+(-[a-z]+)*", clue):
        clue = ""

    try:
        hint_number = int(data.get("number", fallback_n))
    except (TypeError, ValueError):
        hint_number = fallback_n
    hint_number = max(1, min(MAX_HINT_NUMBER, hint_number))

    target_lookup = {word.lower(): word for word in remaining_targets}
    raw_targets = data.get("targets", []) or []
    if not isinstance(raw_targets, list):
        raw_targets = []

    intended_targets = []
    seen = set()
    for value in raw_targets:
        key = str(value).strip().lower()
        if key in target_lookup and key not in seen:
            intended_targets.append(target_lookup[key])
            seen.add(key)

    explanation = str(data.get("reasoning", "") or "").strip()
    explanation = limit_words(explanation, 60)

    return clue, hint_number, intended_targets, explanation


def choose_fallback_hint(used_hints, board_words=None):
    used_hint_set = set(used_hints or [])
    board_words = board_words or []
    for hint in FALLBACK_HINTS:
        if hint not in used_hint_set and not is_hint_too_close_to_board(hint, board_words):
            return hint
    for hint in ["marker", "north", "south", "east", "west"]:
        if hint not in used_hint_set and not is_hint_too_close_to_board(hint, board_words):
            return hint
    return "signal"


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
    fallback_size_cap=2,
    condition="baseline",
):
    if isinstance(bomb_words, str) or bomb_words is None:
        bomb_words = [bomb_words] if bomb_words else []
    used_hint_set = set(previous_hints(history) + (used_hints or []))
    if forbidden_hint:
        used_hint_set.add(forbidden_hint.lower())
    board_words = target_words + neutral_words + list(bomb_words)
    fallback_number = remaining_target_count(target_words, history)
    found_targets = {
        guess
        for item in history
        for guess in item.get("correct_guesses", [])
    }
    remaining_targets = [word for word in target_words if word not in found_targets]

    last_raw = ""
    total_time = 0.0
    attempts = 0
    for _ in range(3):
        attempts += 1
        try:
            raw, elapsed = call_openai_chat(
                HINT_SYSTEM_PROMPT,
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
        hint, hint_number, intended_targets, explanation = parse_hint_json(
            raw, fallback_number, remaining_targets
        )
        if not intended_targets:
            intended_targets = remaining_targets[:hint_number]
        hint_number = min(hint_number, len(intended_targets), fallback_number)
        intended_targets = intended_targets[:hint_number]
        if (
            hint
            and hint not in used_hint_set
            and not is_hint_too_close_to_board(hint, board_words)
            and intended_targets
        ):
            return {
                "hint": hint,
                "hint_number": hint_number,
                "intended_targets": intended_targets,
                "explanation": explanation,
                "raw_response": last_raw,
                "response_time_sec": round(total_time, 3),
                "attempts": attempts,
                "used_fallback": False,
            }

    fallback_targets = remaining_targets[: min(fallback_size_cap, fallback_number)]
    return {
        "hint": choose_fallback_hint(used_hint_set, board_words),
        "hint_number": max(1, len(fallback_targets)),
        "intended_targets": fallback_targets,
        "explanation": "Fallback clue selected because the model did not return a usable JSON clue after retries.",
        "raw_response": last_raw,
        "response_time_sec": round(total_time, 3),
        "attempts": attempts,
        "used_fallback": True,
    }


def generate_ai_hint(
    target_words,
    bomb_words,
    neutral_words,
    word_type,
    history=None,
    used_hints=None,
    round_summaries=None,
    condition="baseline",
):
    return _generate_hint_with_forbidden(
        target_words,
        bomb_words,
        neutral_words,
        word_type,
        history or [],
        used_hints or [],
        round_summaries or [],
        forbidden_hint=None,
        fallback_size_cap=2,
        condition=condition,
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
    condition="baseline",
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
        fallback_size_cap=1,
        condition=condition,
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

WHEN TO REFUSE
- Output exactly REROLL_HINT only if the clue is genuinely meaningless or unrelated to every available board word. Last resort.
- Output exactly SKIP_CLUE only if skipping is allowed AND no available word has at least a plausible score of 3. Last resort.

OUTPUT FORMAT — strict JSON only, no markdown, no commentary outside the JSON. Schema:
{
  "reasoning": "<one or two short sentences explaining the direct everyday link for each guess; logged for research, hidden from the player>",
  "guesses": ["<exact board word>", "..."]
}

OR, instead of JSON, exactly one of these two literal tokens on a single line:
REROLL_HINT
SKIP_CLUE
"""


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
    condition="baseline",
):
    available_board = [word for word in board if word not in previous_guesses]
    word_type_per_card = st.session_state.get("word_type_per_card", {})
    feedback_block = ""
    if condition == "adaptive":
        feedback_block = (
            "\n\nPrevious participant feedback:\n"
            f"{format_all_participant_feedback(history, round_summaries or [])}"
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
        "Interaction history so far this round:\n"
        f"{format_interaction_history(history)}\n\n"
        "Memory from previous rounds:\n"
        f"{format_round_memory(round_summaries or [])}\n\n"
        f"{feedback_block}\n\n"
        "Default to guessing. REROLL_HINT and SKIP_CLUE are last resorts. "
        "Respond with the JSON object OR a single literal token."
    )


def build_guess_repair_prompt(
    board,
    hint,
    max_guesses,
    previous_guesses,
    previous_response,
):
    available_board = [word for word in board if word not in previous_guesses]
    return (
        f"Available board words (choose only exact words from this list): {', '.join(available_board)}\n"
        f"Words already guessed and forbidden: {', '.join(previous_guesses) or '(none)'}\n"
        f"Clue: \"{hint}\"\n"
        f"N: {max_guesses}\n\n"
        "Your previous response was unusable or did not contain enough exact board words:\n"
        f"{previous_response}\n\n"
        "Return strict JSON only. Pick the top N exact board words by direct, everyday semantic association. "
        "Do not add unrelated filler. Schema: "
        '{"reasoning":"short reason","guesses":["Exact board word"]}'
    )


def parse_guess_json(raw_text, available_board, max_guesses):
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(data, dict):
        return []

    raw_guesses = data.get("guesses", []) or []
    if not isinstance(raw_guesses, list):
        return []

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
    return valid


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
    condition="baseline",
):
    history = history or []
    previous_guesses = previous_guesses or []
    available_board = [word for word in board if word not in previous_guesses]

    meta = _empty_ai_call_meta()
    raw = ""
    try:
        raw, elapsed = call_openai_chat(
            GUESS_SYSTEM_PROMPT,
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
            return {"action": "reroll", "guesses": [], **meta}
        if upper == "SKIP_CLUE" and can_skip and remaining_skips > 0:
            return {"action": "skip", "guesses": [], **meta}

        valid_guesses = parse_guess_json(raw, available_board, max_guesses)

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

        if len(valid_guesses) < min(max_guesses, len(available_board)):
            try:
                repair_raw, repair_elapsed = call_openai_chat(
                    GUESS_SYSTEM_PROMPT,
                    build_guess_repair_prompt(
                        board,
                        hint,
                        max_guesses,
                        previous_guesses,
                        raw,
                    ),
                    temperature=0.0,
                    model=GUESS_MODEL_NAME,
                    json_mode=True,
                )
                repaired_guesses = parse_guess_json(
                    repair_raw, available_board, max_guesses
                )
                meta["raw_response"] = f"{raw}\n\n<repair_response>\n{repair_raw}"
                meta["response_time_sec"] = round(
                    (meta["response_time_sec"] or 0.0) + repair_elapsed, 3
                )
                meta["attempts"] = 2
                if len(repaired_guesses) > len(valid_guesses):
                    valid_guesses = repaired_guesses
            except Exception as error:
                meta["raw_response"] = (
                    f"{meta['raw_response']}\n\n<repair_error: {error}>"
                )

        if valid_guesses:
            return {"action": "guess", "guesses": valid_guesses[:max_guesses], **meta}

    if can_skip and remaining_skips > 0:
        return {"action": "skip", "guesses": [], **meta}
    if remaining_rerolls > 0:
        return {"action": "reroll", "guesses": [], **meta}
    return {"action": "guess", "guesses": [], **meta}


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
        "Interaction history with intended targets and explanations:\n"
        f"{format_interaction_history(history)}\n"
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
