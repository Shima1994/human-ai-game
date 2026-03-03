Human–AI Cooperative Word Game (Inspired by Codenames)
This project implements a cooperative word association game where a human player and an AI model take turns giving clues and guessing target words. The game is designed to study collaboration, shared strategy formation, and interaction quality between humans and large language models in a controlled, lightweight environment.

🎮 Game Features
Two gameplay modes: abstract words and concrete words

Turn-taking between human and AI

AI-generated clues using OpenAI’s API

Scoring system and round-based structure

Post-round rating form for evaluating collaboration quality

Simple browser-based interface built with Streamlit

🌐 Online Version
The game is deployed on Streamlit Cloud and can be played directly in the browser:

👉 https://human-ai-word-game-inspired-by-codenames.streamlit.app/

No installation is required.

🛠 Running Locally
To run the game on your local machine:

Create a folder:

Code
.streamlit
Inside it, create a file:

Code
secrets.toml
Add your OpenAI API key:

Code
OPENAI_API_KEY = "your-key-here"
Install dependencies:

Code
pip install -r requirements.txt
Run the app:

Code
streamlit run app.py
📁 Project Structure
Code
human-ai-game/
│
├── app.py                # Main Streamlit application
├── requirements.txt      # Required Python packages
├── README.md             # Project documentation
└── .streamlit/           # Contains secrets.toml (excluded from GitHub)
🎓 Research Context
This project is part of a Master’s thesis and aims to investigate:

Human–AI cooperative behavior

How language models generate clues in constrained tasks

Differences between abstract and concrete word associations

User experience and perceived collaboration quality

The game provides a controlled environment for studying interaction patterns and shared decision-making between humans and AI systems.
