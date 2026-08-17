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

Conditions are assigned when a participant profile is registered, not on ordinary Streamlit reruns. Assignment alternates persistently using `data/sessions.csv`:

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

- In round 1, the participant presses **Ask AI for a clue**, giving them time to inspect the initial board.
- In later rounds, AI clues are generated automatically when the screen loads.
- Before selecting cards, the participant writes a 3–30 word English rationale.
- After the turn, a rating is required. If the human was the clue-giver, a 3–20 word English clue explanation is also required.

### Human clue-giver / AI guesser

- The participant enters a one-word English clue and `N`.
- The participant marks intended targets, predicts the AI guesses, and rates expected understanding.
- The AI returns guesses plus a research rationale.
- The result is previewed in History and is committed with **Save this turn**.

### Full and partial skips

At most two skips are available per round, and a skip is unavailable on the final possible turn.
Each active clue has a configurable countdown (currently 120 seconds). A timeout consumes the turn without submitting guesses or consuming a skip.
When a human skips an AI clue, the AI's next clue retries the same unresolved intended targets with a different clue. Adaptive sessions may use the participant's recorded interpretation and reflection to improve that repair; baseline sessions retry the targets without receiving reflection context.

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
- Turn-level human clue explanations require 3–20 words and normally may not name board cards.
- The board-word restriction is removed after a bomb ends the round because hidden information is no longer at risk.
- End-of-round human feedback requires 3–200 English words.

## Architecture

```text
app.py                    Streamlit entry point and screen routing
core/
  ai_service.py           Prompt construction, OpenAI calls, parsing, retries
  constants.py            Models, scoring, limits, and data paths
  game_logic.py           Board generation, turns, skips, scoring, summaries
  state.py                Session-state initialization and resets
  storage.py              CSV schemas, migration, local logging, GitHub mirror
  validation.py           Board-word detection for explanations
  words.py                Abstract/concrete word banks and board templates
ui/
  components.py           Board, hint, status, and History components
  screens.py              Consent, profile, gameplay, reflection, and results
  study_documents.py      Information sheet, consent, and debriefing text
  styles.py               Responsive CSS and visual tokens
AI_PROMPTS.md              Prompt and condition-isolation documentation
data/                      Runtime CSV output
```

## Data model

Six CSV files are maintained under `data/`:

| File | Grain | Purpose |
| --- | --- | --- |
| `sessions.csv` | one row per session | participant profile, condition, completion, final questionnaire |
| `rounds.csv` | one row per round | normalized board, role, outcome, score, timing |
| `turns.csv` | one row per turn | normalized guesses, alignment, timing, reflection, model metadata |
| `events.csv` | one row per event | timestamped UI/game audit trail with JSON payload |
| `game_rounds.csv` | one row per round | wide backward-compatible research export |
| `game_interactions.csv` | one row per turn | wide backward-compatible interaction export |

`session_id`, `participant_id`, `condition`, `round_number`, and `turn_number` are the primary join keys. Exact schemas are defined by the field lists in `core/storage.py`; these lists are the source of truth.

Important turn-level fields include:

- clue, `N`, intended cards, expected guesses, actual guess order;
- correct, incorrect, neutral, and bomb selections;
- `outcome`, alignment status, error type, and score contribution;
- `skipped`, `skipped_by`, `partial_skip`, `completed_guesses`, and `skipped_guesses`;
- `skip_interpreted_cards`, their word types, and interpretation count;
- counterfactual wrong-guess replacements, actor, word types, count, and AI-call metadata;
- raw and sanitized human/AI explanations plus validation status and block reason;
- reflection rating and timing;
- raw LLM response, parsed response, model, temperature, retries, and latency;
- `repair_applied_to_next_prompt` and condition-specific repair context.

### Serialization conventions

- Normalized tables (`sessions.csv`, `rounds.csv`, `turns.csv`, `events.csv`) use JSON strings for nested arrays/objects where appropriate.
- Legacy wide exports use semicolon-separated values for many list columns and JSON for ordered structures such as `guess_order_json`.
- Booleans are written consistently as `true`/`false` in normalized dict-based tables; legacy exports retain integer-compatible `0`/`1` fields where required.
- Timestamps are recorded as UTC ISO-8601 strings. Older rows may be timezone-naive but are UTC by convention.
- Raw invalid explanations are retained for audit; sanitized fields are blank when validation fails.

`storage.py` includes schema migration and a repair path for legacy `game_interactions.csv` rows that were historically written with two duplicated values. Existing recoverable rows are realigned before the current schema is written.

## Durable storage

Local CSV files are always written. On Streamlit Community Cloud, local storage is ephemeral, so `game_rounds.csv` and `game_interactions.csv` can also be mirrored to GitHub.

Configure `.streamlit/secrets.toml`:

```toml
OPENAI_API_KEY = "your-openai-key"

GITHUB_TOKEN = "token-with-repository-contents-write-access"
GITHUB_REPO = "owner/repository"
GITHUB_BRANCH = "main"
GITHUB_ROUND_CSV_PATH = "data/game_rounds.csv"
GITHUB_INTERACTION_CSV_PATH = "data/game_interactions.csv"
GITHUB_SESSIONS_CSV_PATH = "data/sessions.csv"
```

Condition allocation uses the remote sessions file as an optimistic transaction when GitHub is configured, so a Streamlit instance restart does not reset alternation. On the first deployment of `sessions.csv`, the allocator seeds itself from the last condition in the existing remote round export. Completed session snapshots preserve demographics and final-questionnaire values remotely. Round and interaction exports are mirrored after every completed round.

GitHub Contents API writes use optimistic retries for update conflicts. For high-volume or multi-instance production data collection, a transactional database/object store is preferable to GitHub-backed CSV because GitHub is not an atomic multi-table database. Normalized `rounds.csv`, `turns.csv`, and `events.csv` remain local in the current implementation; their durable equivalents are the remote wide exports plus remote session snapshots.

## Installation and local execution

Python 3.11+ is recommended.

```bash
python -m venv .venv
# Activate the environment for your operating system
pip install -r requirements.txt
streamlit run app.py
```

Set `OPENAI_API_KEY` in `.streamlit/secrets.toml`. The default models are configured in `core/constants.py` and currently use `gpt-4o` for clue generation, guessing, turn explanation, and round reflection.

## Verification

At minimum, run:

```bash
python -m compileall app.py core ui
```

Recommended study-release checks additionally include:

- schema field uniqueness;
- schema/row length equality for both legacy exports;
- a synthetic round write through all local CSV writers;
- baseline prompt leak tests using sentinel rationale/reflection values;
- adaptive/baseline alternation tests;
- full-skip, partial-skip, bomb, all-targets-found, and four-turn termination scenarios;
- desktop and mobile Streamlit smoke tests.

## Research purpose

The application supports a Master's thesis on intersubjective alignment in human–AI collaboration. Its central comparison is whether exchanging and reusing short explanations improves subsequent coordination relative to a baseline that collects the same explanation data without sharing it between teammates.
