# Human–AI Cooperative Word Game

A Streamlit app for a study on shared understanding between a person and an AI teammate. The two play a word-association game inspired by Codenames.

There are two conditions, `adaptive` and `baseline`. Both collect the same data. They differ in one thing: whether the explanations and reflections of each teammate are passed on to the other.

## The game

A session has four rounds. In each round one teammate gives the clues and the other guesses. The roles swap every round.

There are four fixed boards (`B01`–`B04` in `core/words.py`). Every participant sees the same words; only the card positions are shuffled. Each board has 16 cards:

- 5 targets (2 abstract, 3 concrete)
- 9 neutral cards (5 abstract, 4 concrete)
- 2 bombs (1 abstract, 1 concrete)

No word appears on more than one board.

The clue-giver gives one English word and a number `N`. The guesser then picks `N` cards one by one, and each card is revealed at once. The guesser may also skip. A round ends when all targets are found, when a bomb is picked, or after three completed turns.

### Points, stars, medal and bonus

- A target scores **+2** if the clue-giver meant it and **+1** otherwise. A neutral card scores 0.
- A round earns a **star** when all five targets are found without a bomb.
- The points of all four rounds (at most 40) decide the final medal: bronze from 10, silver from 20, gold from 30.
- Participants who complete the study get a **bonus of £1 per star, or £5 for all four stars**. It is paid through Prolific after the study. The round summary shows the bonus so far, and the final page shows the total. The amount follows from `final_star_count` on the completed session row (`star_bonus_gbp` in `core/game_logic.py`).

## Conditions

| | `adaptive` | `baseline` |
| --- | --- | --- |
| Human reasons and reflections are collected | Yes | Yes |
| AI reasoning and explanations are collected | Yes | Yes |
| The human sees the AI's explanations and reflection | Yes | No |
| The AI gets the human's explanations, ratings and reflections | Yes | No |
| The AI keeps a memory of the whole game | Yes | No |
| The AI gets the game facts (clues, guesses, results, skips) | Yes | Yes |

In both conditions the AI gets the same game rules (as the participant's guide states them), the same text about the bonus, and the turns used and targets left. No prompt names the condition. `AI_PROMPTS.md` describes every prompt.

### Assignment

The condition is assigned once, when the participant registers. There are 16 cells: 2 conditions × 2 starting roles × 4 board orders (`core/assignment.py`). The board orders form a balanced 4×4 Latin square (Williams design), so every board appears once in every round position.

Each new participant gets the cell with the fewest participants. A cell counts sessions that were completed or were active in the last 20 minutes, so an abandoned session frees its cell. The choice happens inside a locked database transaction and is stored in the `assignments` table, so two people who register at the same moment are counted correctly.

Because completed sessions count, pilot and test sessions have to be removed from the tables before the main study.

## What the participant does

### When the AI gives the clue

1. In the first turn of the round, the participant presses **Ask AI for a clue** when ready. Later turns get their clue automatically.
2. Before picking any card, they write a short reason (3–30 English words, no card names).
3. After the turn, they rate how well they understood the AI's clue. If they picked a neutral card, they also say which card they would have picked instead.

### When the participant gives the clue

1. They enter a one-word English clue and `N`.
2. Before the AI guesses, they mark the cards they meant, predict the AI's picks, rate how well they expect the AI to understand, and write the **General link** (3–20 English words, no card names).
3. The AI guesses. Its reason is shown only in `adaptive`.
4. They rate how well the AI understood their clue.

### After each round

The participant writes a short reflection (3–200 English words) and then answers four statements from 1 (strongly disagree) to 5 (strongly agree), each starting with "In this round". One statement depends on the role: "I understood what the AI meant" is asked when the AI gave the clues, and "I could predict how the AI would interpret my clues" when the participant gave them. After round 2, a second attention check sits among these statements.

The AI answers the same statements from its own side of the round. Its answers are stored for analysis and never shown.

## Skips and time limits

Each round allows two skips. A skip before any card is picked does not use one of the three turns. A skip after at least one card (a partial skip) counts as a completed turn, and the cards already picked count. Before skipping, the guesser (human or AI) names the cards they think the clue was meant for. After a skip, the next clue is encouraged, but not forced, to try those targets again.

- **Clue-giver:** 120 seconds. When they run out, a pop-up gives 30 more seconds once per clue. After that, the turn is lost.
- **Guesser:** 90 seconds, with a warning 30 seconds before the end. If time runs out before any card is picked, one skip is used; cards already picked still count. With both skips used, the guesser gets a last 30 seconds, and if those also run out the round ends without a star.

The AI's own time is not counted. Each AI request has a separate 20-second technical timeout and a small number of retries.

## Input checks

- Clues must be one English word. They may not be a board word or close to one, and may not repeat within the same round.
- Written answers must be in English (ASCII letters).
- Reasons and the General link may not name a card on the board. The end-of-round reflection may, because all cards are revealed by then.

## Project structure

```text
app.py                    Entry point and screen routing
core/
  ai_service.py           Prompts, OpenAI calls, parsing, retries
  assignment.py           The 16 counterbalancing cells
  constants.py            Models, points, bonus, timers and limits
  db.py                   Database connection, tables, assignment, flat views
  game_logic.py           Rounds, turns, skips, points, stars, bonus
  prolific.py             Prolific link parameters, completion code, attention checks
  state.py                Session state at the start
  storage.py              What is stored in each table
  tutorial.py             Practice rounds (never stored as study data)
  validation.py           Checks for card names in written answers
  words.py                The four boards
ui/
  components.py           Board, status bar, rating scale, history
  screens.py              All screens of the study
  game_guide.py           Written guide
  guide_walkthrough.py    Visual guide
  study_documents.py      Information sheet, consent and debriefing
  styles.py               Loads static/app.css
static/                   CSS and fonts
.streamlit/config.toml    Streamlit settings
tests/                    pytest tests
AI_PROMPTS.md             The AI prompts and what each condition sees
DEPLOYMENT.md             Running the app on a server
```

## Data

All data goes to a Postgres database (Supabase). Each table has a few real columns for joining and filtering, and a `data` JSONB column with every field. The field lists in `core/storage.py` (`SESSIONS_LOG_FIELDS`, `ROUNDS_LOG_FIELDS`, `TURNS_LOG_FIELDS`, `EVENTS_LOG_FIELDS`) define exactly which fields are stored.

| Table | One row per | Real columns |
| --- | --- | --- |
| `sessions` | session | `participant_id`, `session_id`, `condition`, `completed`, `last_completed_stage` |
| `rounds` | round | `session_id`, `round_number`, `condition` |
| `turns` | turn | `session_id`, `round_number`, `turn_number`, `condition`, `action_type`, `alignment_applicability` |
| `board_cards` | card in a round | `session_id`, `round_number`, `board_instance_id`, `card_word`, `card_role`, `word_type` |
| `events` | event | `session_id`, `participant_id`, `condition`, `round_number`, `turn_number`, `event_type`, `timestamp` |
| `assignments` | registered session | `session_id`, `cell_index`, `condition`, `starting_role`, `board_order`, `assigned_at` |
| `condition_counter` | (single row) | used to lock the assignment; not study data |

The views `sessions_flat`, `rounds_flat` and `turns_flat` show every JSON field as its own text column, for analysis in SQL, pandas or R. The tables join on `session_id`, `round_number` and `turn_number`.

Missing values are stored as an empty string. Timestamps are in UTC (ISO 8601). Lists and longer structures are stored as JSON.

### Main fields

**Turns:** the clue and `N`, the cards the clue-giver meant, the predicted picks, the actual picks in order, which picks were targets, neutral or bombs, points, skips and the cards named at a skip, replacement cards after a wrong pick, the human's reason or General link, the AI's explanation, the human's and the AI's timing, and the raw AI response with model, prompt version and latency.

**Ratings per turn** (each field holds the answer to one question and is empty when the question was not asked):

- `human_expected_ai_understanding_rating`: before the AI guesses, "How well do you expect the AI to understand your clue?"
- `human_rating_ai_understood_my_clue`: after the AI guessed, "How well do you think the AI understood your clue?"
- `human_rating_i_understood_ai_clue`: after the human guessed, "How well do you think you understood the AI's clue?"

**Rounds:** whether all targets were found, whether a bomb was hit, `round_star`, `total_stars_so_far`, `round_end_reason` (`all_targets_found`, `bomb`, `completed_turn_limit` or `timeout_loss`), the AI's reflection, the human's reflection, the human's answers (`round_questionnaire_*`) and the AI's answers (`ai_round_questionnaire_*`).

**Sessions:** the Prolific IDs, the profile answers, both attention checks (a submission counts as failed only when both are failed), `final_star_count`, the completion code, `run_type` (`participant`, `pilot` or `test`), and the versions of the experiment, schema, code, deployment and models.

## Running it locally

To run the app on a server, see [DEPLOYMENT.md](DEPLOYMENT.md).

Use Python 3.12; the app is developed and tested with it.

```bash
python -m venv .venv
# activate the environment
pip install -r requirements.txt
streamlit run app.py
```

Put the keys in `.streamlit/secrets.toml` (this file is not committed):

```toml
OPENAI_API_KEY = "your-openai-key"
DATABASE_URL = "postgresql://USER:PASSWORD@HOST:PORT/DBNAME"
```

For Supabase, take the *Transaction pooler* connection string, which works over IPv4. Environment variables with the same names take precedence over this file. The models are set in `core/constants.py` (currently `gpt-5.4-2026-03-05`).

To run the tests:

```bash
pip install -r requirements-dev.txt
pytest
```

The tests use no database and no OpenAI key.

## Research purpose

This app is part of the Master's thesis *"Investigating Intersubjective Alignment in Human–AI Collaboration Through a Cooperative Word Association Game"*. It compares whether sharing and reusing short explanations between the teammates improves their coordination, against a baseline that collects the same explanations without sharing them.
