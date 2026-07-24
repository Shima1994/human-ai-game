# AI Prompt and Model-Interaction Specification

This document describes every model interaction currently implemented in `core/ai_service.py`, including condition-specific context, parsing, fallback behavior, and stored research fields. The Python source remains authoritative if this document and code ever diverge.

## Models and shared API wrapper

Models are configured in `core/constants.py`:

| Constant | Current default | Purpose |
| --- | --- | --- |
| `HINT_MODEL_NAME` | `gpt-4o` | AI clue generation and clue rerolls |
| `GUESS_MODEL_NAME` | `gpt-4o` | AI card selection and partial-skip decision |
| `REFLECTION_MODEL_NAME` | `gpt-4o` | AI turn explanations and round reflections |

All requests pass through:

```python
call_openai_chat(
    system_prompt,
    user_prompt,
    *,
    temperature,
    model,
    json_mode,
)
```

The wrapper reads `OPENAI_API_KEY` from Streamlit secrets, optionally loads `.env`, calls the chat-completions API, and returns `(response_text, elapsed_seconds)`.

## Condition boundary

The experiment has two conditions with identical data collection but different communication context.

### Adaptive

Adaptive prompts may include:

- ordinary game facts;
- intended targets and expected guesses;
- guess rationales;
- human understanding ratings;
- valid human clue explanations;
- valid AI explanations;
- end-of-round human feedback and AI reflection;
- persistent cross-round teammate memory.

`format_all_participant_feedback(...)`, `format_round_memory(...)`, and `format_persistent_teammate_memory(...)` support this condition.

### Baseline

Baseline prompts receive only task-relevant game facts:

- clue and clue number;
- available and previously guessed board cards;
- correct and incorrect selections;
- neutral/bomb outcome;
- skip state;
- round success, bomb, and medal facts.

Baseline context is built with `format_baseline_history(...)` and `format_baseline_round_memory(...)`. It excludes intended cards, expected guesses, rationales, ratings, human explanations, AI explanations, and end-of-round feedback. Dedicated baseline system prompts also remove persistent-teammate-memory instructions.

The UI separately prevents AI reasoning/explanations from being shown to the human in baseline. Raw responses and parsed explanations are still stored for research analysis.

## 1. AI clue generation

Functions:

```python
generate_ai_hint(...)
generate_ai_hint_reroll(...)
```

Used when the AI is clue-giver and the human is guesser. In round 1 generation starts after the participant presses **Ask AI for a clue**; in later AI-clue rounds it starts automatically.

### System behavior

The model is told that the board contains 16 cards: 5 targets, 9 neutrals, and 2 bombs. It must produce a safe one-word English clue that is not a board word or morphological variant. It evaluates all neutrals and both bombs before choosing a target cluster.

### Output schema

Clue generation uses forced JSON mode:

```json
{
  "reasoning": "short research reasoning",
  "clue": "one-word-clue",
  "number": 2,
  "targets": ["Exact target", "Exact target"],
  "expected_guesses": ["Exact board card", "Exact board card"]
}
```

Rules enforced by parsing and validation:

- `clue` is normalized to lowercase English letters/hyphens;
- `number` is bounded by the configured maximum and remaining targets;
- targets must be exact remaining target cards;
- expected guesses must be exact currently available board cards;
- used clues and board-word variants are rejected;
- `number`, target count, and returned lists are reconciled before acceptance.

### Runtime context

Both conditions receive:

- word type and per-card word types;
- remaining targets and targets already found;
- available board cards;
- all neutrals and bombs;
- previously used/forbidden clues;
- condition-appropriate history and round memory.

Adaptive additionally receives participant feedback and persistent teammate memory. Baseline receives fact-only memory.

### Call and fallback

- Temperature: `0.55`.
- JSON mode: enabled.
- Maximum initial attempts: three.
- A reroll forbids the rejected clue and uses a more conservative fallback cap.
- If all model attempts fail validation, a curated fallback clue is selected after board-word filtering.

### Stored fields

- parsed clue and `N`;
- intended targets and expected guesses;
- `hint_explanation` (the parsed reasoning);
- `hint_raw_response`;
- `hint_response_time_sec` and total hint time;
- `hint_attempts`;
- `hint_used_fallback`.

The raw clue-generation reasoning is research data and is not directly rendered as the gameplay clue explanation.

## 2. AI guessing a human clue

Function:

```python
ai_guess(...)
```

The AI sees only available card labels, the human clue, `N`, skip availability, and condition-appropriate history. It never receives the current hidden roles while acting as guesser.

### Normal and skip JSON

```json
{
  "action": "guess",
  "reasoning": "3–30 words explaining the selected cards",
  "guesses": ["Exact board card", "Exact board card"]
}
```

or:

```json
{
  "action": "partial_skip",
  "reasoning": "The first two are strong; the remaining choice risks a bomb.",
  "guesses": ["Exact board card", "Exact board card"],
  "interpreted_cards": ["Likely intended card", "Another likely intended card"]
}
```

A partial skip is accepted only when:

- skipping is currently allowed;
- at least one skip remains;
- at least one valid guess is supplied;
- fewer than `N` valid guesses are supplied.

Completed guesses are retained and scored; the remaining guesses are abandoned; one full skip is consumed.

For both `action="skip"` and `action="partial_skip"`, `interpreted_cards` contains only unselected exact board cards that the AI thinks the clue-giver probably meant. Its maximum length equals the number of abandoned guesses (`N - completed guesses`). It is stored separately from cards the AI actually committed as guesses.

### Control responses

The model may instead return the reroll literal:

```text
REROLL_HINT
```

Full skip is represented by JSON `action="skip"` with no completed guesses and a non-empty `interpreted_cards` list. Actions are honored only when the corresponding action remains available.

### Parsing and repair

1. Recognize the literal reroll token.
2. Parse JSON and filter guesses against exact available board cards.
3. Read `action` as `guess`, `partial_skip`, or `skip`.
4. If JSON fails, attempt conservative comma/newline token parsing.
5. If a normal response contains fewer than `N` usable guesses, make one JSON repair call at temperature `0.0`.
6. Do not repair a valid partial skip into unsafe filler guesses.
7. If no guesses remain usable, fall back to an allowed full skip/reroll rather than inventing cards.

Primary-call temperature is `0.2`; forced JSON mode is disabled so the reroll literal remains possible.

### Condition-specific visibility

- Adaptive: the AI rationale may be displayed in History and is available to later adaptive memory.
- Baseline: the rationale is collected and logged but is neither displayed to the human nor passed to later prompts.

### Stored fields

- action and ordered guesses;
- `guess_rationale` and word count;
- raw and parsed response;
- response and total guess timing;
- retry/repair metadata;
- full/partial skip fields and actor;
- the guesser's separate `skip_interpreted_cards`, word types, and count;
- post-outcome replacement cards for non-bomb wrong guesses, including raw-response and timing metadata;
- completed and abandoned guess counts;
- correctness, alignment, error type, and bomb outcome.

## 3. AI turn explanation

Function:

```python
generate_ai_turn_explanation(...)
```

After a human finishes guessing an AI clue—including a full or partial skip—the AI produces a short general explanation of its own clue relationship.

Output schema:

```json
{
  "relationship_type": "short category label",
  "explanation": "one general sentence without board-card names"
}
```

The application checks the explanation against all board words. Invalid responses are retried; if generation remains invalid, a safe fallback is stored with a validation flag and block reason.

Adaptive may show the sanitized explanation to the human. Baseline stores it but does not show or reuse it.

Stored fields include raw/sanitized explanation, validity, block reason, relationship type, and reflection source.

## 4. AI end-of-round reflection

Function:

```python
generate_ai_round_reflection(...)
```

The model summarizes clue interpretation, successes, errors, skips, and one actionable improvement. Maximum requested length is 180 words; returned text is capped at 200 words.

- Temperature: `0.4`.
- Adaptive context may contain full interaction history.
- Baseline context uses fact-only history and therefore excludes human/AI explanation exchange.
- Adaptive displays the reflection and may reuse it in later memory.
- Baseline stores it without displaying or reusing it.

## 5. Human-input validation relevant to prompts

Human clues are validated locally before any AI call:

- exactly one English word;
- not equal or morphologically close to a board card;
- not previously used in the round.

Human explanation inputs are also local validations:

- ASCII English text with at least one English letter;
- guess rationale: 3–30 words;
- human clue explanation: 3–20 words;
- end-of-round feedback: 3–200 words;
- board-card names are blocked in turn explanation while hidden information remains relevant;
- after a bomb ends the round, card names are permitted.

Invalid raw text and its block reason can be retained for research audit, while sanitized fields remain empty.

## 6. Prompt/data audit fields

The normalized `turns.csv` includes model and prompt audit columns:

- `llm_model`;
- `llm_temperature`;
- `llm_prompt_version`;
- `llm_system_prompt_version`;
- `llm_response_raw`;
- `llm_response_parsed`;
- `llm_error`;
- `llm_latency_seconds`;
- `repair_applied_to_next_prompt`;
- `repair_context_used`.

All datasets include `condition`. Researchers should use the normalized tables for analysis and treat `game_rounds.csv` / `game_interactions.csv` as backward-compatible wide exports.

## 7. Safety and reproducibility notes

- Model outputs remain stochastic; raw responses and latency are retained for audit.
- Fallback use and repair attempts must be included as covariates when relevant.
- Baseline leakage tests should inject sentinel explanation strings and assert that they do not occur in either initial or repair prompts.
- Prompt changes should be versioned in code before production data collection; the current generic prompt-version fields are not a substitute for release tags or commit hashes.
