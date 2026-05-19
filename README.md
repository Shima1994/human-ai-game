# Human–AI Cooperative Word Game (Inspired by *Codenames*)

This project implements a cooperative word association game where a human player and an AI model take turns giving clues and guessing target words. The game is designed to study collaboration, shared strategy formation, and interaction quality between humans and large language models in a controlled, lightweight environment.

## 🎮 Game Features
- Two gameplay modes: **abstract words** and **concrete words**
- Turn-taking between human and AI
- AI-generated clues using OpenAI’s API
- Scoring system and round-based structure
- Before/after AI-guess ratings plus end-of-round reflection notes
- Simple browser-based interface built with Streamlit

## Data Storage on Streamlit Cloud

Streamlit Cloud's local filesystem is not durable, so production CSV data should be written to GitHub through repository secrets.

Add these secrets in Streamlit Cloud:

```toml
GITHUB_TOKEN = "github_pat_or_classic_token_with_repo_contents_write"
GITHUB_REPO = "your-username/your-repo"
GITHUB_BRANCH = "main"
GITHUB_ROUND_CSV_PATH = "data/game_data_rounds.csv"
GITHUB_INTERACTION_CSV_PATH = "data/game_interactions.csv"
```

The app still writes local CSV files as a fallback, but GitHub CSV logging is the durable path for public tests and Amazon Mechanical Turk.

## AI Prompts

All AI prompts are documented in `AI_PROMPTS.md`.

## 🌐 Online Version
The game is deployed on Streamlit Cloud and can be played directly in the browser:

👉 **https://human-ai-word-game-inspired-by-codenames.streamlit.app/**

No installation is required.

## 🛠 Running Locally
To run the game on your local machine:

1. Create a folder:
.streamlit
2. Inside it, create a file:
secrets.toml
3. Add your OpenAI API key:
OPENAI_API_KEY = "your-key-here"
4. Install dependencies:
pip install -r requirements.txt
5. Run the app:
streamlit run app.py

## 📁 Project Structure
human-ai-game/ │ 
├── app.py # Main Streamlit application
├── requirements.txt # Required Python packages 
├── README.md # Project documentation 
└── .streamlit/ # Contains secrets.toml (excluded from GitHub)


## 🎓 Research Context
This project is part of a Master’s thesis and aims to investigate:
- Human–AI cooperative behavior  
- How language models generate clues in constrained tasks  
- Differences between abstract and concrete word associations  
- User experience and perceived collaboration quality  

The game provides a controlled environment for studying interaction patterns and shared decision-making between humans and AI systems.
