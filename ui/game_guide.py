GUIDE_OVERVIEW = """
You and the AI are on the same team.

Your goal is to find all hidden target cards by communicating through word clues, while avoiding the bomb cards.

The study consists of 4 rounds. Each round starts with a new board containing 16 word cards:

- 5 target cards that your team needs to find
- 9 neutral cards
- 2 bomb cards that should be avoided
"""

GUIDE_ROLE = """
During each round, you will have one of two roles:

- Clue-Giver
- Guesser

The AI takes the other role. Your role may change between rounds.
"""

CLUE_GIVER_INTRO = "Your task is to help the AI identify one or more target cards."

CLUE_GIVER_STEPS = (
    (
        "Give a one-word clue",
        """Enter one word that connects the target cards you want the AI to identify.

Try to choose a clue that connects as many target cards as possible.

However, be careful: a clue that is too broad may also lead the AI toward neutral cards or, most importantly, a bomb card.

For example, if two target cards are strongly related to “food”, you might give:

**food — 2**""",
    ),
    (
        "Choose the clue number",
        """After entering your clue, choose how many target cards your clue refers to.

The number tells the AI how many cards you intend it to identify.

For example:

**food — 2**

means that your clue “food” refers to exactly two intended target cards.""",
    ),
    (
        "Select your intended target cards",
        """Next, select exactly the target cards that you intended when creating the clue.

The number of selected intended cards must match your clue number.

For example, if your clue is:

**food — 2**

you must select exactly two intended target cards.""",
    ),
    (
        "Predict what the AI will choose",
        """Before the AI makes its guess, select the cards that you expect the AI to choose.

Select exactly the same number of cards as your clue number.""",
    ),
    (
        "Rate your expected shared understanding",
        """Before seeing the AI's response, rate how well you think the AI will understand your clue.

Use the 1–5 scale shown on the screen.

Choose the rating that best represents your expectation at that moment.""",
    ),
    (
        "Briefly explain the general connection",
        """Briefly describe the general relationship between your clue and the cards you have in mind.

Write 3–20 words in English and do not mention any words currently shown on the board.""",
    ),
)

CLUE_GIVER_OUTRO = "After completing these steps, submit your clue and the AI will respond."

GUIDE_SECTIONS = (
    (
        "When the AI Is the Clue-Giver",
        """When the AI is the Clue-Giver, it will give you:

- a one-word clue
- a number

Your task is to interpret the clue and select the cards that you believe the AI intended.

For example:

**animal — 2**

means that the AI is trying to communicate two cards that it believes are related to “animal”.

Select the number of cards indicated by the clue number.

Think about the relationship between the clue and the words on the board, but remember that some apparently related cards may be neutral cards or bombs.""",
    ),
    (
        "Targets, Neutral Cards, and Bombs",
        """The safest way to score well is to identify the intended target cards while avoiding incorrect cards.

**Target cards:**

These are the cards your team is trying to find.

**Neutral cards:**

These are safe cards, but they are not targets. Selecting them does not help your team complete the round.

**Bomb cards:**

These are the most dangerous cards. Selecting a bomb immediately ends the round.

When you are the Clue-Giver, try to choose clues that strongly connect your intended targets while being clearly different from the bomb cards and unrelated cards.

When you are the Guesser, consider the clue carefully before making your selections.""",
    ),
    (
        "Try to Connect More Than One Target",
        """A clue can refer to more than one target card.

Finding several target cards with one clue is more efficient than finding them one at a time.

For example, if three target cards share a meaningful connection, you may give a clue with the number 3.

However, larger clue numbers can also make the clue harder to interpret.

Your goal is therefore not simply to choose the largest possible number. Try to communicate as many targets as you can without making the clue dangerously ambiguous.""",
    ),
    (
        "Interactions and Round Limit",
        """Each round allows a maximum of 3 completed interactions.

An interaction is one clue-and-response exchange between you and the AI.

A round can end earlier if:

- all 5 target cards are found, or
- a bomb card is selected.

Otherwise, the round ends when the maximum of 3 completed interactions has been reached.""",
    ),
    (
        "Skipping",
        """Sometimes a clue may be difficult to understand or you may not feel confident enough to continue.

You may use the Skip option up to 2 times within a round.

If you skip before submitting a card selection, the skip does not use one of the three completed interaction opportunities.

If you have already submitted a behavioural response before using Skip, that interaction still counts as a completed interaction.

Skipping is therefore available as a safety mechanism when communication is unclear, but the number of skips is limited.""",
    ),
    (
        "Communicative Repair",
        """A misunderstanding does not always end the communication.

After an unresolved interaction, the game may allow the communication to continue through a repair attempt.

Repair gives the communicating partner another opportunity to clarify the intended relationship.

When a repair occurs, it remains connected to the unresolved meaning from the previous interaction rather than starting an unrelated communication attempt.

Use the new information carefully and reconsider the remaining intended cards.""",
    ),
    (
        "Time Limit",
        """When it is your turn to make a decision, you have 90 seconds to complete the required actions shown on the screen.

The timer applies to your decision time.

Time used by the AI to generate its response does not count against your 90 seconds.

If the timer reaches zero before you complete your action, that interaction is used and the game continues.

A timeout does not use one of your skips.

Try to answer carefully, but do not wait until the final seconds to submit your response.""",
    ),
    (
        "After an Interaction",
        """During the game, you may be asked to provide a short rating or reflection about the interaction.

These questions are part of the research study.

Please answer based on your actual understanding and experience during that interaction.

There are no “correct” answers to these reflection questions.""",
    ),
    (
        "Medals and Performance",
        """Your goal is to find all 5 target cards as efficiently as possible.

If all targets are found:

- in 1 or 2 completed interactions → Gold Medal
- in 3 completed interactions → Silver Medal

If the targets are not all found within the available interactions, or if a bomb is selected, the round is not completed successfully.

The medal is simply feedback about your performance in the game.""",
    ),
)

GUIDE_REMINDERS = """
- You and the AI are teammates.
- Find all 5 target cards.
- Avoid the 2 bomb cards.
- When giving a clue, provide one word and a number.
- The number tells your partner how many cards the clue refers to.
- When you are the Clue-Giver, select the exact cards you intended.
- When asked, predict which cards you think the AI will choose.
- Give your 1–5 understanding rating before seeing the AI's response.
- Briefly explain the general relationship behind your clue.
- When guessing, select the number of cards indicated by the clue.
- Try to connect several targets when this can be done safely.
- You have a maximum of 3 completed interactions per round.
- You may use Skip up to 2 times per round.
- Avoid bomb cards — selecting one ends the round immediately.
- Answer reflection questions based on your genuine experience.

The game will guide you through each step, so you do not need to memorize all of these instructions before starting.
"""
