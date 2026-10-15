# Human–AI Cooperative Word Game

A Streamlit research application for studying shared understanding between a human participant and an AI teammate in a constrained, Codenames-inspired word-association task.

The study has two automatically balanced conditions. Both collect the same behavioral, performance, rating, and explanation data. They differ only in whether explanation and reflection information is exchanged and reused during collaboration.

## Study design

Each session contains four rounds. The human and AI alternate between clue-giver and guesser roles; the starting role is randomized per session.

Each round uses a 16-card mixed board:

- 5 target cards;
- 9 neutral cards;
- 2 bomb cards;
- a controlled abstract/concrete composition determined by board template A or B;
- no word reuse within the same four-round session.

The clue-giver supplies one English clue and a number `N`. The guesser may select up to `N` cards. A bomb ends the round immediately. A round also ends when all targets are found or three turns have been used.

Medals are awarded only when all five targets are found without a bomb:

| Turns used | Medal | Score |
| --- | --- | ---: |
| 1–2 | Gold | 5 |
| 3 | Silver | 4 |
| Unfinished or bomb | None | 0 |

## Experimental conditions

Conditions are assigned when a participant profile is registered, not on ordinary Streamlit reruns. Assignment alternates persistently using a single-row counter (`condition_counter`) in Postgres, updated inside a `SELECT ... FOR UPDATE` transaction so two participants registering at the same instant cannot be assigned the same slot:

```text
adaptive → baseline → adaptive → baseline → ...
```

The first/default condition remains `adaptive`. Every output table includes `condition`, allowing all session-, round-, turn-, and event-level records to be joined and analyzed by treatment.

| Behavior | `adaptive` | `baseline` |
| --- | --- | --- |
| Collect human rationales and reflections | Yes | Yes |
| Collect AI reasoning and explanations | Yes | Yes |
| Show AI explanations/reasoning to the human | Yes | No |
| Pass human explanations/ratings to later AI prompts | Yes | No |
| Pass persistent teammate-model memory to AI | Yes | No |
| Pass ordinary game facts (clue, N, guesses, correctness, skips, bomb outcome) | Yes | Yes |

Baseline prompt construction uses dedicated fact-only history formatters. Intended cards, expected guesses, rationales, ratings, explanations, and end-of-round feedback are excluded from baseline model context.

## Interaction flow

### AI clue-giver / human guesser

- On the first turn of every AI-clue round, the participant presses **Ask AI for a clue**, giving them time to inspect the new board before the timer starts; later turns of the round get their clue automatically.
- In later rounds, AI clues are generated automatically when the screen loads.
- Before the board unlocks, the participant rates how well they understand the AI's clue and writes a 3–30 word English rationale.
- After the turn, the participant rates the shared understanding in both directions: how well they understood the AI, and how well they think the AI understood them.

### Human clue-giver / AI guesser

- The participant enters a one-word English clue and `N`.
- The participant marks intended targets, predicts the AI's guesses, and rates expected understanding before the AI guesses.
- The AI returns guesses plus a research rationale.
- The result is previewed in History and is committed with **Save this turn**, then the same bidirectional shared-understanding rating is collected.

After every round, the participant answers four 1–5 agreement statements about that round (the former end-of-game items, each framed as "In this round", e.g. "In this round, I felt that I understood what the AI meant when it gave clues"). Two items fit only one role: understanding the AI's clues is asked only in rounds where the AI gives the clues, predicting how the AI would interpret the participant's clues only in rounds where the AI guesses; the item that does not apply stays blank in that round's row. After round 2 (one guessing and one clue-giving round), the second attention check sits among them. The AI privately answers the mirrored statements about the same round. Its self-report is generated via the LLM, logged for analysis, and never shown to the participant. There is no separate end-of-game questionnaire.

### Full and partial skips

At most two skips are available per round independently of the three completed-turn limit. A full skip consumes no completed turn; a partial skip retains its completed guesses as one interaction and does not add another turn for the repair action.

Each human clue-giving or guessing task has a configurable decision countdown, rendered as a component that triggers ordinary Streamlit reruns (via `streamlit-autorefresh`) rather than a browser reload, so an expiring timer never wipes session state. Giving a clue is harder than guessing one, so it gets more time: currently 120 seconds for the clue-giver and 90 seconds for the guesser. When the clue-giver's 120 seconds run out, a pop-up gives them 30 extra seconds, once per clue; only when those also run out is it a timeout (turn field `clue_extra_time_used`, event `clue_extra_time_granted`). The practice clue round in the tutorial uses the same 120 + 30 seconds. AI/API calls use a separate, much shorter 20-second technical timeout per request, bounded further by a capped retry with backoff (at most 2–3 attempts depending on the call, short delays between them, and `max_retries=1` on the OpenAI client itself) — this never reduces the participant's decision window. A human timeout consumes the turn without submitting guesses or consuming a skip.

Repair after a skip is encouraged, never forced, in both directions. When a human skips an AI clue, the AI's next clue is asked to strongly consider the same unresolved intended targets (with a different clue) but may add or choose other targets. Adaptive sessions may use the participant's recorded interpretation and reflection to improve that repair; baseline sessions receive the targets without reflection context. When the AI skips a human clue, the human sees a neutral reminder naming their own unresolved intended cards, while remaining free to choose any targets.

- **Full skip:** no card is selected; the clue is abandoned; one full skip is consumed.
- **Partial skip:** one or more guesses are retained, their correctness is recorded, the remaining guesses are abandoned, and one full skip is consumed.

Humans can stop mid-turn with **Stop guessing and use 1 skip**. The AI may return `action="partial_skip"` with fewer than `N` strong guesses when the remaining choices are dangerously uncertain. Partial skip is preferred over a serious bomb risk, but is accepted only when a skip remains and `0 < completed guesses < N`.

Before either a human or the AI uses a full or partial skip, it records the remaining unselected cards it believes the clue-giver most likely intended. Already selected cards are excluded, and the maximum selection count equals the number of abandoned guesses. These `skip_interpreted_cards` are stored separately from completed guesses. Adaptive sessions may show and reuse this interpretation; baseline sessions collect it for analysis but never display it or include it in later prompts.

After a non-bomb turn containing one or more wrong neutral guesses, the guesser also records exactly the same number of alternative cards they would choose instead. Humans answer this in the reflection step; the AI answers through a separate post-outcome call after learning which of its choices were wrong. Adaptive sessions share and reuse these alternatives, while baseline sessions only store them.

## Input validation

- Human clues must be exactly one English word.
- Clues may not equal or closely match a board word and may not repeat within a round.
- Human rationales and reflections must contain English ASCII text; Persian, Arabic, Japanese, mixed-script, and other non-ASCII responses are rejected.
- Guess rationales require 3–30 words.
- Pre-AI human clue explanations require 3–20 English words and may never name board cards, including when the resulting turn ends the round.
- The board-word restriction is removed after a bomb ends the round because hidden information is no longer at risk.
- End-of-round human feedback requires 3–200 English words.

## Architecture

```text
app.py                    Streamlit entry point and screen routing
core/
  ai_service.py           Prompt construction, OpenAI calls, parsing, retries/backoff
  constants.py            Models, scoring, timers, and other tunable limits
  db.py                   Postgres connection, schema, atomic condition allocation, flat views
  game_logic.py           Board generation, turns, skips, scoring, summaries
  state.py                Session-state initialization (incl. request-derived device/locale defaults)
  storage.py              Field-list schemas and row-builders that persist into Postgres
  tutorial.py             Practice-round content and logic (isolated from real study data)
  validation.py           Board-word detection for explanations
  words.py                Abstract/concrete word banks and board templates
ui/
  components.py           Board, hint, status bar, rating scale, and History components
  screens.py              Consent, profile, gameplay, reflection, and results screens
  game_guide.py            Onboarding/guide copy shown before the study starts
  study_documents.py      Information sheet, consent, and debriefing text
  styles.py               Reads, minifies, and injects static/app.css
static/
  app.css                  All app CSS (plain stylesheet, not embedded in Python)
  fonts/                   Self-hosted font files
.streamlit/
  config.toml              enableStaticServing, showErrorDetails="none", gatherUsageStats=false
  secrets.toml              OPENAI_API_KEY, DATABASE_URL (not committed)
tests/                      pytest suite (unit tests + Streamlit AppTest screen smoke tests)
AI_PROMPTS.md              Prompt and condition-isolation documentation
```

## Data model

All experimental data is written to Postgres (a managed Supabase instance in the current deployment) via `core/db.py`. Each table keeps a small number of real, indexed columns used for joins and filtering, plus one `data JSONB` column holding every field for that row — the field lists in `core/storage.py` (`SESSIONS_LOG_FIELDS`, `ROUNDS_LOG_FIELDS`, `TURNS_LOG_FIELDS`, `EVENTS_LOG_FIELDS`) are the source of truth for exactly which keys live in that JSON document.

| Table | Grain | Real (indexed) columns |
| --- | --- | --- |
| `sessions` | one row per session | `participant_id`, `session_id`, `condition`, `completed`, `last_completed_stage` |
| `rounds` | one row per round | `session_id`, `round_number`, `condition` |
| `turns` | one row per turn | `session_id`, `round_number`, `turn_number`, `condition`, `action_type`, `alignment_applicability` |
| `board_cards` | one row per board card per round | `session_id`, `round_number`, `board_id`, `card_word`, `card_role`, `word_type` |
| `events` | one row per event | `session_id`, `participant_id`, `condition`, `round_number`, `turn_number`, `event_type`, `timestamp` |
| `condition_counter` | single row | atomic alternation counter (not experimental data) |

`board_cards` is a fully flat table (every card's word/role/word_type as real columns, no JSON) so a card-level query — e.g. "how often was each target word actually guessed" — never requires unpacking JSON.

For analysts who prefer plain SQL/pandas/R over unpacking JSON, three read-only views expand each JSONB `data` column into one text column per field: `sessions_flat`, `rounds_flat`, `turns_flat`. These are created (and recreated, since Postgres won't let `CREATE OR REPLACE VIEW` reorder columns) by `core/db.py:ensure_flat_views`, called once per process from `core/storage.py`.

`session_id`, `participant_id`, `condition`, `round_number`, and `turn_number` are the primary join keys.

Important turn-level fields include:

- clue, `N`, intended cards, expected guesses, actual guess order;
- correct, incorrect, neutral, and bomb selections;
- `outcome`, `bomb_hit`, alignment status, error type, and score contribution;
- action-sequence `turn_number`, `completed_turn_number`, `skip_number`, `skipped_by`, `partial_skip`, `completed_guesses`, and `skipped_guesses`;
- `skip_interpreted_cards`, their word types, and interpretation count;
- `missed_intended_targets` and `extra_correct_guesses` (set differences between intended and actual guesses);
- counterfactual wrong-guess replacements, actor, word types, count, and AI-call metadata;
- raw and sanitized human/AI explanations plus validation status and block reason;
- `hint_explanation` and `hint_attempts`;
- explicit per-turn timing: `hint_time_sec`, `guess_time_sec`, `human_decision_time_sec`, `reflection_time_sec`, separate from LLM latency;
- raw LLM response, parsed response, model, temperature, retries, and latency;
- `repair_applied_to_next_prompt`, immediate `repair_source_turn`, stable `repair_chain_id`, and `repair_attempt_number` for repeated repairs;
- canonical `action_type` and `alignment_applicability` classifications derived from the raw action fields without changing stored outcome metrics.

Round-level fields additionally include `ai_round_reflection` and `human_round_feedback`, the AI's and the human's end-of-round messages to each other, and the end-of-round questionnaire: the participant's `round_questionnaire_i_understood_ai_clues`, `round_questionnaire_predict_ai_interpretation`, `round_questionnaire_adapted_to_ai_behavior`, `round_questionnaire_reflection_helped`, `round_questionnaire_shared_understanding` and `round_questionnaire_json`, and the AI's private mirrored self-report `ai_round_questionnaire_i_understood_human_clues`, `ai_round_questionnaire_predict_human_interpretation`, `ai_round_questionnaire_adapted_to_human_behavior`, `ai_round_questionnaire_reflection_helped`, `ai_round_questionnaire_shared_understanding`, `ai_round_questionnaire_reasoning` and the full `ai_round_questionnaire_json`.

Until schema 2.1.0 these ratings were asked once at the end of the game and stored on the session row (`post_game_*`, `ai_post_game_*`); those sessions keep them in their `data` JSON.

Turn metrics use the live game outcome: `hit_rate` is target guesses divided by all submitted guesses, `target_yield` and `turn_score_delta` are newly found targets, and `jaccard_alignment` compares intended and guessed-card sets. Skip/timeout rows have zero outcome metrics because no guesses were finalized; unavailable legacy/incomplete metrics remain blank.

Rating fields represent different stages and directions, not one mutual score. Each field holds the answer to exactly one question and is blank on turns where that question is not asked:

- `human_expected_ai_understanding_rating` — turns where the human gives the clue, before the AI guesses: "How well do you expect the AI to understand your clue?"
- `human_rating_ai_understood_my_clue` — the same turns, after the AI's guesses (or skip): "How well do you think the AI understood your clue?"
- `human_rating_i_understood_ai_clue` — turns where the AI gives the clue, after the human's guesses (or skip): "How well do you think you understood the AI's clue?"

Until schema 2.1.0 a single field, `human_perceived_understanding_rating`, held the post-turn answer to different questions depending on the role and on whether guesses were made; those sessions keep it in their `data` JSON.
- `human_explanation_*` is the canonical pre-AI General Link, with `human_explanation_source=pre_ai_human_clue_form` and `human_explanation_collected_at` marking its origin and submission time.
- `human_round_feedback` is the qualitative end-of-round response. The five `round_questionnaire_*` round fields are the human's per-round questionnaire items (1 = strongly disagree, 5 = strongly agree); the `ai_round_questionnaire_*` fields are the AI's mirrored self-report for the same round. `attention_check_mid_game_answer` (session) is the second attention check, shown among the round 2 questions; the first is `attention_check_profile_answer` on the profile page. A submission counts as failed only when both are failed.

### Serialization conventions

- Nested arrays/objects (card lists, LLM raw responses, the AI questionnaire, etc.) are stored as JSON inside each row's `data` column, or as JSON strings within the flat views' text columns.
- Booleans are native Postgres `BOOLEAN` values (`true`/`false`), not CSV-style strings.
- Timestamps are recorded as UTC ISO-8601 strings (timezone-aware, `+00:00` suffix).
- Raw invalid explanations are retained for audit; sanitized fields are blank when validation fails.

### Provenance and lifecycle

New session rows record `experiment_version`, `schema_version`, `code_commit`, `deployment_version`, `model_identifier`, and `condition_assignment_version`. The source-controlled defaults identify the current pilot and schema. Deployments should provide exact platform identifiers through `CODE_COMMIT` (or `GITHUB_SHA`, `STREAMLIT_GIT_COMMIT`, or `RENDER_GIT_COMMIT`) and `DEPLOYMENT_VERSION`. Unavailable identifiers remain blank; timestamps are never substituted for version identifiers. `model_identifier` records the exact configured model aliases and does not claim that a mutable provider alias is an immutable model snapshot.

Session lifecycle fields are updated only at persisted stage boundaries: participant profile, tutorial, saved gameplay rounds, post-study questionnaire (the last round's questions), and completed debriefing. `last_completed_stage` means the last successfully completed stage, not the currently displayed page. `session_end_reason` is blank for an incomplete or disappeared session and is `completed` only after the participant acknowledges the debriefing. There is currently no explicit participant-withdrawal action or terminal technical-error route, so `withdrawal_requested` and `technical_termination` remain false rather than inferring intent from browser disappearance, AI errors, skips, timeouts, or game outcomes.

Normalized turn `action_type` values are `interaction`, `full_skip`, `partial_skip`, and `timeout`. `alignment_applicability` values are `observed_completed_selection`, `partial_selection`, `interpreted_only_skip`, `timeout_no_behavioral_selection`, and `not_applicable`. Existing Jaccard and hit-rate values are unchanged; this metadata identifies structural placeholder zeros. Normalized round `round_end_reason` values produced by the current state machine are `all_targets_found`, `bomb`, and `completed_turn_limit`. Retryable technical events are not round terminations.

## Storage

All experimental data is written directly to Postgres — there is no local CSV or GitHub mirroring step. `core/db.py` creates the schema on first use (`ensure_schema`, idempotent, cached per process) and every write is an `INSERT ... ON CONFLICT DO UPDATE` upsert keyed by the table's real columns, so retried/rerun writes are safe. `log_event` failures are caught and reported into `st.session_state.remote_log_status`/`remote_log_error` rather than raising, so a transient database issue degrades gracefully instead of crashing the participant's session.

Configure `.streamlit/secrets.toml`:

```toml
OPENAI_API_KEY = "your-openai-key"
DATABASE_URL = "postgresql://postgres:[PASSWORD]@<host>:5432/postgres"
```

`DATABASE_URL` is the direct Postgres connection string (Supabase: Project Settings → Database → Connection string → URI), not the REST API URL/key shown elsewhere in a Supabase project.

Condition allocation reads and increments `condition_counter` inside a single `SELECT ... FOR UPDATE` transaction, so Postgres itself serializes concurrent registrations — there is no optimistic-retry or CAS logic to reason about, and a Streamlit instance restart does not reset alternation.

## Installation and local execution

Python 3.11+ is recommended.

```bash
python -m venv .venv
# Activate the environment for your operating system
pip install -r requirements.txt
streamlit run app.py
```

Set `OPENAI_API_KEY` and `DATABASE_URL` in `.streamlit/secrets.toml` (see Storage above). The default models are configured in `core/constants.py` and currently use the pinned snapshot `gpt-5.4-2026-03-05` for clue generation, guessing, turn explanation, and round reflection.

## Verification

Run the test suite:

```bash
pip install -r requirements-dev.txt
pytest
```

This is a mix of behavioral unit tests (game logic, validation, storage row-shaping, condition allocation) and some tests that check the presence of specific code/CSS rather than exercising behavior — a known gap, not a design goal. `streamlit.testing.v1.AppTest` (bundled with Streamlit) can drive a real screen end-to-end — fill in widgets, click buttons, assert no unhandled exception — without making real OpenAI calls or Postgres writes as long as those code paths aren't triggered; it is the intended direction for replacing the source-grepping tests, but that migration hasn't happened yet.

Recommended study-release checks additionally include:

- schema field uniqueness (`core/storage.py`'s `*_LOG_FIELDS` lists);
- baseline prompt leak tests using sentinel rationale/reflection values;
- adaptive/baseline alternation tests;
- full-skip, partial-skip, bomb, all-targets-found, and four-turn termination scenarios;
- desktop and mobile Streamlit smoke tests;
- a real round played end-to-end against the live Supabase instance before each deployment, with the test rows deleted afterward.

## Research purpose

The application supports a Master's thesis titled *"Investigating Intersubjective Alignment in Human–AI Collaboration Through a Cooperative Word Association Game"*. Its central comparison is whether exchanging and reusing short explanations improves subsequent coordination relative to a baseline that collects the same explanation data without sharing it between teammates.
