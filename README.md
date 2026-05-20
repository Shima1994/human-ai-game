# Human–AI Cooperative Word Game (Inspired by *Codenames*)

This project implements a cooperative word association game where a human player and an AI model take turns giving clues and guessing target words. It is designed to study collaboration, shared strategy formation, and interaction quality between humans and large language models in a controlled, lightweight environment.

## 🎮 Game features

- Four fixed 15-word boards, with targets, bomb, and neutral cards randomized each run
- Two gameplay modes: **abstract words** and **concrete words**
- Turn-taking between human and AI
- AI-generated clues using OpenAI's API (JSON-mode prompts with chain-of-thought reasoning saved for analysis only)
- Scoring system, medal tiers, and round-based structure
- Before/after AI-guess ratings plus end-of-round AI reflection and human feedback
- AI clue *reasoning* is **never shown to the player during the game** — it is saved per turn for post-hoc research analysis
- Mobile-first responsive UI with the Inter font family and a consistent color system

## 🧠 AI prompts

All AI prompts are documented in `AI_PROMPTS.md`.

- Hints, guesses, and end-of-round reflections all use `gpt-4o` by default (configurable in `core/constants.py`).
- The clue-giver uses structured JSON output (`response_format={"type": "json_object"}`) with retries — this eliminates the parse failures that previously made the AI output literal placeholders.
- Each turn captures the raw model response, response time, retry count, and whether a fallback was used.

## 📦 Data storage

Two CSV files are written under `data/`:

| File | Granularity |
| --- | --- |
| `data/game_rounds.csv` | One row per round |
| `data/game_interactions.csv` | One row per turn (clue, guess, or skip) |

Both files include a `session_id` (UUID generated per game) so all rows for one play-through can be joined together.

### `game_rounds.csv` columns

```
session_id, timestamp_utc, participant_id, round, role, word_type, board, targets, bomb,
neutral_words, clues_used, guesses, turns, skips, targets_found, any_target_correct,
all_targets_found, bomb_hit, medal, score_change, round_duration_sec, perception_rating_end,
ai_round_reflection, human_round_feedback
```

### `game_interactions.csv` columns

```
session_id, timestamp_utc, participant_id, round, role, word_type, turn, clue_giver, guesser,
hint, hint_number, intended_targets, hint_explanation, guesses, correct_guesses,
missed_intended_targets, extra_correct_guesses, neutral_guesses, bomb_guess, outcome,
skipped, skipped_by, bomb_hit, round_medal, round_success, ai_understanding_rating_before,
ai_understanding_rating_after, hint_response_time_sec, hint_attempts, hint_used_fallback,
guess_response_time_sec, hint_raw_response, guess_raw_response, interaction_recorded_at
```

List-valued columns (`board`, `targets`, `neutral_words`, `intended_targets`, `guesses`, etc.) are stored as `;`-separated strings, which loads cleanly with `pandas`:

```python
import pandas as pd
df = pd.read_csv("data/game_interactions.csv")
df["intended_targets"] = df["intended_targets"].fillna("").str.split(";")
```

`hint_raw_response` and `guess_raw_response` contain the model's full raw output for that turn (intended for analysis, never displayed in the UI).

## ☁️ Data storage on Streamlit Cloud

Streamlit Cloud's local filesystem is not durable, so production CSV data is also written to GitHub through repository secrets.

Add these secrets in Streamlit Cloud:

```toml
GITHUB_TOKEN = "github_pat_or_classic_token_with_repo_contents_write"
GITHUB_REPO = "your-username/your-repo"
GITHUB_BRANCH = "main"
GITHUB_ROUND_CSV_PATH = "data/game_rounds.csv"
GITHUB_INTERACTION_CSV_PATH = "data/game_interactions.csv"
```

The app still writes local CSV files as a fallback, but GitHub CSV logging is the durable path for public tests and Amazon Mechanical Turk. The token must have repository contents write access.

## 🌐 Online version

The game is deployed on Streamlit Cloud and can be played directly in the browser:

👉 **https://human-ai-word-game-inspired-by-codenames.streamlit.app/**

No installation is required.

## 🛠 Running locally

1. Create a folder named `.streamlit` inside the project root.
2. Inside it, create a file named `secrets.toml`.
3. Add your OpenAI API key:
   ```toml
   OPENAI_API_KEY = "your-key-here"
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Run the app:
   ```bash
   streamlit run app.py
   ```

## 📁 Project structure

```
.
├── app.py                  # Streamlit entrypoint
├── requirements.txt
├── AI_PROMPTS.md           # Full prompt documentation
├── core/
│   ├── ai_service.py       # All OpenAI calls and JSON parsing
│   ├── constants.py        # Models, scoring, file paths
│   ├── game_logic.py       # Round flow, interaction recording
│   ├── state.py            # Streamlit session state defaults
│   ├── storage.py          # CSV schema and GitHub mirroring
│   └── words.py            # The four fixed boards
├── ui/
│   ├── components.py       # Board, history, hint cards
│   ├── screens.py          # Welcome, clue-giver, guesser, summary, game-over
│   └── styles.py           # CSS tokens, fonts, mobile breakpoints
└── data/                   # Local CSV output (created at runtime)
```

## 🎓 Research context

This project is part of a Master's thesis and aims to investigate:

- Human–AI cooperative behavior
- How language models generate clues in constrained tasks
- Differences between abstract and concrete word associations
- User experience and perceived collaboration quality

The game provides a controlled environment for studying interaction patterns and shared decision-making between humans and AI systems.
