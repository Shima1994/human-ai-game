# AI Prompts

This file documents every prompt sent to the AI model in the game, where it is used, and what runtime data is injected into the prompt.

## Models

Models are configured in `core/constants.py`:

| Variable | Default | Used by |
| --- | --- | --- |
| `HINT_MODEL_NAME` | `gpt-4o` | AI clue generation (and reroll) |
| `GUESS_MODEL_NAME` | `gpt-4o` | AI guessing the human clue |
| `REFLECTION_MODEL_NAME` | `gpt-4o` | End-of-round AI reflection |

## Shared model call

All AI requests go through `call_openai_chat(system_prompt, user_prompt, *, temperature, model, json_mode)` in `core/ai_service.py`.

- `system`: the role-specific instruction block below.
- `user`: round-specific board state, history, and memory.
- For clue generation the call uses `response_format={"type": "json_object"}`. The guesser does not require JSON mode (it can also reply with single-token control codes `REROLL_HINT` or `SKIP_CLUE`), but is instructed to use a JSON object for normal guesses.
- The call returns `(text, elapsed_seconds)`. The elapsed time is stored per turn in `data/game_interactions.csv` (`hint_response_time_sec` and `guess_response_time_sec`).
- The raw model response is also stored in `data/game_interactions.csv` (`hint_raw_response` and `guess_raw_response`) for research analysis.

## 1. AI clue generation

Functions:

- `generate_ai_hint(...)` — initial clue.
- `generate_ai_hint_reroll(...)` — replacement clue when the previous one was rejected or skipped.

When it runs:

- Human is the guesser.
- The AI must return strict JSON containing a reasoning trace, a one-word clue, a count N, and the intended target words.
- The reasoning trace is saved for analysis but is **never shown to the player during gameplay**.

System prompt (`HINT_SYSTEM_PROMPT`):

```text
You are an expert clue-giver in a cooperative Codenames-style word game. You are partnered with one human teammate. Your shared goal is to find all target words quickly without picking the bomb.

GAME RULES
- The board has 15 cards. Hidden roles: 5 targets (good), 1 bomb (round-ending), 9 neutrals (safe but wrong).
- You output one English clue word and a number N. Your teammate then guesses N words from the board.
- The clue word must NOT appear on the board and must NOT be a morphological variant (no plural / verb-form / spelling trick).
- A great clue links 2 or 3 targets through one vivid, everyday association that any literate adult would recognize instantly.

HOW TO PICK A GREAT CLUE (think like a thoughtful human teammate)
1. Scan the remaining targets and group them into candidate clusters. Look for shared categories (animals, sports, kitchen), idioms ("breaking the ice"), famous pairings ("salt and pepper"), sensory imagery, or cultural archetypes.
2. For each candidate clue, mentally test it against EVERY neutral and the BOMB.
   - If the clue could reasonably point at a neutral, the teammate will probably pick that neutral. Lower N or pick a safer clue.
   - If the clue has ANY plausible link to the bomb, throw it away.
3. Prefer concrete, common, mainstream associations over clever or obscure ones. Your teammate is human and short on time.
4. Aim for the largest safe cluster. But a confident N=2 always beats a shaky N=4.
5. Avoid being a simple synonym of a single target. Reach for a richer concept that bridges multiple targets.
6. Use the round history. If a previous clue confused the teammate, do not reuse the same association style; switch angle. If a clue worked well, build on what they understood.
7. Never use the same clue word twice in a round.

OUTPUT FORMAT — strict JSON only, no markdown, no commentary outside the JSON. Schema:
{
  "reasoning": "<one or two short sentences: which targets you chose, what the link is, and why the bomb and neutrals are not at risk>",
  "clue": "<one lowercase English word, letters only; a hyphen is allowed only in idiomatic compounds>",
  "number": <integer between 1 and 5>,
  "targets": ["<exact remaining target word as spelled in the input>", "..."]
}

CONSTRAINTS
- "number" must equal the length of "targets".
- "targets" must be a subset of the remaining target words listed in the user message.
- "clue" must not appear on the board nor be a morphological variant.
- "reasoning" is logged for research analysis and is NEVER shown to the player during gameplay.
```

User prompt (built by `build_hint_user_prompt`):

```text
Word type for this round: {word_type}
Remaining target words (you must aim only at these): {remaining_targets}
Targets already found this round: {found_targets or (none)}
Neutral words (AVOID — your clue must not fit these): {neutral_words}
BOMB word (NEVER let your clue fit this): {bomb_word}

Forbidden clue words (already used this round, do not repeat): {used_hints or (none)}

Interaction history so far this round (use it to learn what your teammate understood and what they missed):
{format_interaction_history(history)}

Memory from previous rounds in this game:
{format_round_memory(round_summaries)}

Produce the best one-word clue you can, then explain (in the reasoning field) the link and why each neutral and the bomb are safe. Respond with the JSON object only.
```

For `generate_ai_hint_reroll(...)` the previously rejected clue is added to the forbidden list and the fallback intended-target cap is reduced to 1.

Call settings: `temperature=0.55`, `response_format={"type":"json_object"}`, up to 3 retries.

Expected output (example):

```json
{"reasoning":"Police and King both deal with authority and lawmaking, and 'law' is a common everyday concept that does not fit any neutral or the bomb.","clue":"law","number":2,"targets":["Police","King"]}
```

Storage:

- The parsed clue, number, intended targets, and reasoning are saved per turn in `data/game_interactions.csv` (`hint_explanation`).
- The full raw response is stored in `hint_raw_response`.
- The model response time is stored in `hint_response_time_sec`.
- The number of retries used is stored in `hint_attempts`.
- A boolean `hint_used_fallback` records whether the fallback word list had to be used.

Fallback: If JSON parsing fails three times in a row, the code falls back to a curated word list (`FALLBACK_HINTS`) that is filtered against the board. The fallback hint and reasoning are still logged.

## 2. AI guessing the human clue

Function: `ai_guess(...)`.

When it runs:

- Human gives the clue.
- AI either picks N board words, asks for a reroll, or skips the clue.

System prompt (`GUESS_SYSTEM_PROMPT`):

```text
You are an expert semantic guesser in a cooperative Codenames-style word game. Your human teammate just gave you a clue word and a number N. Your job: pick exactly N words from the available board that a normal human would most likely mean.

GAME RULES
- The board has 15 words. Some are good targets, some are neutral (safe but wrong), one is a bomb (round-ending).
- You only see the clue and the words — never the hidden roles.
- Hitting the bomb ends the round with zero points.

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
```

User prompt (built by `build_guess_user_prompt`):

```text
Available board words (only choose from these): {available_board}
Words already guessed this round (do NOT repeat): {previous_guesses}

Your teammate's clue: "{hint}"
Number of guesses to produce (N): {max_guesses}

Before answering, internally rank every available board word by direct semantic association to the clue. Your final guesses must be the top N exact board words, not random filler.

Skipping allowed right now: {yes/no}
Remaining skips this round: {remaining_skips}
Remaining clue rerolls: {remaining_rerolls}

Interaction history so far this round:
{format_interaction_history(history)}

Memory from previous rounds:
{format_round_memory(round_summaries)}

Default to guessing. REROLL_HINT and SKIP_CLUE are last resorts. Respond with the JSON object OR a single literal token.
```

Call settings: `temperature=0.2`, no forced JSON mode (so the model can return either JSON or one of the literal tokens). Parsing is layered:

1. If the trimmed response equals `REROLL_HINT` (and rerolls remain), the action is `reroll`.
2. If it equals `SKIP_CLUE` (and skipping is allowed), the action is `skip`.
3. Otherwise the response is parsed as JSON and the `"guesses"` list is filtered against the available board.
4. If JSON parsing fails, a comma/newline-split fallback parses tokens.
5. If fewer than N valid words are found, a second repair call is made with `json_mode=True` and `temperature=0.0`.
6. If no usable guesses are found after repair, the AI skips/rerolls when allowed instead of adding random filler.

Return shape: `{"action": "guess"|"reroll"|"skip", "guesses": [...], "raw_response": str, "response_time_sec": float, "attempts": int}`.

Storage:

- The action and resulting guesses are recorded normally.
- `guess_raw_response` and `guess_response_time_sec` are stored per turn in `data/game_interactions.csv`.

## 3. AI round reflection

Function: `generate_ai_round_reflection(...)`.

When it runs:

- After every round ends, before the human types their own feedback.

System prompt (`REFLECTION_SYSTEM_PROMPT`):

```text
You are an AI teammate writing a short reflection at the end of one round of a cooperative word game. Your reader is the human player.

Your reflection should:
1. If you gave the clues, explain plainly why each clue was meant for which targets, what link you used (category, metaphor, idiom, image), and how you tried to keep the bomb and neutrals safe. Acknowledge any guess that went wrong.
2. If the human gave the clues, compare their marked intended targets to your guesses. Where you misread, say what association pulled you the wrong way. Where you guessed right, say what clicked.
3. Mention any skips and what made the clue feel risky.
4. End with one specific, actionable suggestion the team can apply in the next round.
5. Be warm, plain, and concrete. No empty praise. Maximum 180 words.
```

User prompt:

```text
Round role: {role}
Word type: {word_type}
Targets: {target_words}
Neutral words: {neutral_words}
Bomb: {bomb_word}
All targets found: {round_success}
Bomb hit: {round_bomb_hit}
Medal: {round_medal}

Interaction history with intended targets and explanations:
{format_interaction_history(history)}
```

Call settings: `temperature=0.4`. The response is post-trimmed to a maximum of 200 words as a safety net.

Storage: the reflection is saved in `data/game_rounds.csv` (`ai_round_reflection`) and is also placed in the round memory passed to the next round's prompts.

## 4. Human hint validation

Local validation (no AI call):

- `validate_human_hint(hint, board_words)`
- `validate_human_hint_with_history(hint, board_words, history, used_hints=None)`

Checks:

- Clue is not empty.
- Clue is exactly one English word.
- Clue is not the same as, or morphologically too close to, a board word (matches on raw string, simple stem, and 4+ character prefix overlap).
- Clue has not already been used in this round.

## 5. Saved fields

Round-level CSV (`data/game_rounds.csv`) columns:

```
session_id, timestamp_utc, participant_id, round, role, word_type, board, targets, bomb,
neutral_words, clues_used, guesses, turns, skips, targets_found, any_target_correct,
all_targets_found, bomb_hit, medal, score_change, round_duration_sec, perception_rating_end,
ai_round_reflection, human_round_feedback
```

Interaction-level CSV (`data/game_interactions.csv`) columns:

```
session_id, timestamp_utc, participant_id, round, role, word_type, turn, clue_giver, guesser,
hint, hint_number, intended_targets, hint_explanation, guesses, correct_guesses,
missed_intended_targets, extra_correct_guesses, neutral_guesses, bomb_guess, outcome,
skipped, skipped_by, bomb_hit, round_medal, round_success, ai_understanding_rating_before,
ai_understanding_rating_after, hint_response_time_sec, hint_attempts, hint_used_fallback,
guess_response_time_sec, hint_raw_response, guess_raw_response, interaction_recorded_at
```

- `session_id` is a UUID assigned per game session and links all of a participant's rows together.
- `hint_explanation` contains the AI's "reasoning" field for AI-generated clues and is empty for human-generated clues. It is never shown to the player in the UI.
- `hint_raw_response` and `guess_raw_response` capture the model's full raw response per turn for after-the-fact analysis.
- List-valued fields are stored as semicolon-separated strings, which load cleanly with `pandas.read_csv(...)` and `df[col].str.split(";")`.
