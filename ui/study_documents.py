from html import escape

CONSENT_DOCUMENT = """
# Information Sheet for Participation in Research

## Investigating Intersubjective Alignment in Human–AI Collaboration Through a Cooperative Word Association Game

Shima Ghasempour — [shima.ghasempoour-ardestani@stud.uni-due.de](mailto:shima.ghasempoour-ardestani@stud.uni-due.de)

Department of Human-centered Computing and Cognitive Science

September 2026

## Information for Participants

Thank you for considering participating in this study. This information sheet explains the purpose of the study, what your participation involves, what data will be collected, and your rights as a participant.

### 1. What is the research about?

This study investigates how shared understanding, or intersubjective alignment, develops between a human participant and an AI system during a cooperative word association game. The study focuses on how humans and AI systems interpret clues, make guesses, and recover from misunderstandings through short reflection steps during gameplay.

### 2. Do I have to take part?

No. Participation is voluntary. You may decide not to participate, and you may stop participating at any time during the study without giving a reason. You must be at least 18 years old and sufficiently fluent in English to understand word associations and short instructions.

### 3. What will my involvement be?

You will take part in an online cooperative word association game with an AI system. In each round, either you or the AI will act as the clue-giver, while the other will act as the guesser. The clue-giver gives a one-word clue and a number, and the guesser selects the cards that they think are related to the clue.

Before the game, you will be asked to complete a short demographic questionnaire (e.g., age group, experience with AI tools, and previous experience with word association games).

During the game, you may be asked to provide short ratings and, in some cases, brief explanations about how well a clue was understood. These reflection questions help us understand how shared understanding develops during collaboration.

The study is expected to take approximately 25-30 minutes.

### 4. Are there different versions of the game?

The core game interface is the same for all participants. However, different technical versions of the AI system may be used. These versions differ in whether reflection information is shared between the participant and the AI and whether it supports later communication.

Participants will be assigned automatically to one of the study conditions. The assignment is determined by the system and cannot be selected by participants.

### 5. What data will be collected?

The study will collect anonymous interaction data generated during the game, including:

- game condition and session ID;
- round and turn numbers;
- assigned roles of human and AI;
- clues, clue numbers, guesses, intended cards, selected cards, likely intended cards reported when a skip is used, and alternative cards reported after non-bomb wrong guesses;
- performance measures such as correct guesses, errors, score, and medals;
- alignment measures between intended cards and guessed cards;
- short rating responses and required reflection texts during relevant game steps;
- word type information, such as abstract or concrete word labels;
- demographic categories (e.g., age group, English proficiency, previous experience with AI tools, and previous experience with word association games); a nickname is optional;
- technical information needed for the study, such as timestamps and basic device/browser information.

The game does not request your legal name, address, or email address. If you provide the optional nickname, use a pseudonym rather than your real name.

### 6. What will my information be used for?

The collected information will be used for the purposes of this Master’s thesis project, academic analysis, possible academic publications, and future research on human–AI collaboration.

Only anonymized and aggregated results will be reported. Individual participants will not be identifiable in any publication resulting from this study.

### 7. Will my data be kept confidential and anonymized?

Yes. The collected data will be stored anonymously using session identifiers. The data will not contain direct personal identifiers. Only the researchers involved in the project will have access to the research data.

Results will be reported only in aggregated or anonymized form. Only anonymized data may be shared via open data repositories (e.g. zenodo) to promote open science.

### 8. How can I withdraw from the study?

You may stop participating at any point during the online study by closing the browser window. If you withdraw before completing the study, your partial data may be excluded from the main analysis.

Since the collected data is anonymous, it may not be possible to identify and remove your data after the study has been completed.

### 9. Are there any risks?

This study is considered low risk. You will interact with a word association game and answer short reflection questions. You may stop at any time if you feel uncomfortable.

### 10. Who can I contact if I have questions?

If you have any questions about the study, please use the contact details listed at the top of this information sheet.

---

## Consent Form

## PARTICIPATION IN THIS RESEARCH STUDY IS VOLUNTARY

- I have read and understood the information sheet for this study.
- I am 18 years old or older.
- I understand that demographic categories (e.g., age group and prior experience with AI tools) will be collected for research purposes and that providing a nickname is optional.
- I understand that my participation is voluntary.
- I understand that I can stop participating at any time during the study without giving a reason.
- I understand that I will play a cooperative word association game with an AI system.
- I understand that my clues, guesses, ratings, reflection responses, game logs, and performance data will be collected anonymously for research purposes.
- I understand that different technical versions of the AI system may share and use reflection information differently while the core game mechanics remain the same.
- I understand that no directly identifying personal information will be collected in the game data.
- I understand that anonymized data may be used for academic analysis, the Master’s thesis, possible academic publications, and future research.
- I consent voluntarily to participate in this study.
"""


CONSENT_CHECKLIST_ITEMS = (
    "I have read and understood the information sheet for this study.",
    "I am 18 years old or older.",
    "I understand that demographic categories (e.g., age group and prior experience with AI "
    "tools) will be collected for research purposes and that providing a nickname is optional.",
    "I understand that my participation is voluntary.",
    "I understand that I can stop participating at any time during the study without giving "
    "a reason.",
    "I understand that I will play a cooperative word association game with an AI system.",
    "I understand that my clues, guesses, ratings, reflection responses, game logs, and "
    "performance data will be collected anonymously for research purposes.",
    "I understand that different technical versions of the AI system may share and use "
    "reflection information differently while the core game mechanics remain the same.",
    "I understand that no directly identifying personal information will be collected in "
    "the game data.",
    "I understand that anonymized data may be used for academic analysis, the Master's "
    "thesis, possible academic publications, and future research.",
)


INFORMATION_SHEET_TITLE = (
    "Investigating Intersubjective Alignment in Human–AI Collaboration "
    "Through a Cooperative Word Association Game"
)

INFORMATION_SHEET_INTRODUCTION = (
    "Thank you for considering participating in this study. This information "
    "sheet explains the purpose of the study, what your participation involves, "
    "what data will be collected, and your rights as a participant."
)

INFORMATION_SHEET_SECTIONS = (
    (
        "What is the research about?",
        "<p>This study investigates how shared understanding, or intersubjective "
        "alignment, develops between a human participant and an AI system during "
        "a cooperative word association game. The study focuses on how humans and "
        "AI systems interpret clues, make guesses, and recover from misunderstandings "
        "through short reflection steps during gameplay.</p>",
    ),
    (
        "Do I have to take part?",
        "<p>No. Participation is voluntary. You may decide not to participate, and "
        "you may stop participating at any time during the study without giving a "
        "reason. You must be at least 18 years old and sufficiently fluent in English "
        "to understand word associations and short instructions.</p>",
    ),
    (
        "What will my involvement be?",
        "<p>You will take part in an online cooperative word association game with an "
        "AI system. In each round, either you or the AI will act as the clue-giver, "
        "while the other will act as the guesser. The clue-giver gives a one-word clue "
        "and a number, and the guesser selects the cards that they think are related "
        "to the clue.</p><p>Before the game, you will be asked to complete a short "
        "demographic questionnaire (e.g., age group, experience with AI tools, and "
        "previous experience with word association games).</p><p>During the game, you "
        "may be asked to provide short ratings and, in some cases, brief explanations "
        "about how well a clue was understood. These reflection questions help us "
        "understand how shared understanding develops during collaboration.</p>"
        "<p>The study is expected to take approximately 25-30 minutes.</p>",
    ),
    (
        "Are there different versions of the game?",
        "<p>The game interface is the same for all participants. However, different "
        "technical versions of the AI system may be used in the background. These "
        "versions differ in whether reflection information collected during the "
        "interaction is used to support subsequent communication between the "
        "participant and the AI. Participants will be assigned automatically to one "
        "of the study conditions. The assignment is determined by the system and "
        "cannot be selected by participants.</p>",
    ),
    (
        "What data will be collected?",
        "<p>The study will collect anonymous interaction data generated during the "
        "game, including:</p><ul><li>game condition and session ID;</li><li>round and "
        "turn numbers;</li><li>assigned roles of human and AI;</li><li>clues, clue "
        "numbers, guesses, intended cards, and selected cards;</li><li>performance "
        "measures such as correct guesses, errors, score, and medals;</li><li>alignment "
        "measures between intended cards and guessed cards;</li><li>short rating "
        "responses and optional reflection texts;</li><li>word type information, such "
        "as abstract or concrete word labels;</li><li>optional demographic information "
        "(e.g., age group, English proficiency, previous experience with AI tools, "
        "and previous experience with word association games);</li><li>technical "
        "information needed for the study, such as timestamps and basic device/browser "
        "information.</li></ul>",
    ),
    (
        "",
        "<p>No directly identifying personal information, such as your name, address, "
        "or email address, will be collected in the game data.</p>",
    ),
    (
        "What will my information be used for?",
        "<p>The collected information will be used for the purposes of this Master’s "
        "thesis project, academic analysis, possible academic publications, and future "
        "research on human–AI collaboration. Only anonymized and aggregated results "
        "will be reported. Individual participants will not be identifiable in any "
        "publication resulting from this study.</p>",
    ),
    (
        "Will my data be kept confidential and anonymized?",
        "<p>Yes. The collected data will be stored anonymously using session "
        "identifiers. The data will not contain direct personal identifiers. Only the "
        "researchers involved in the project will have access to the research data. "
        "Results will be reported only in aggregated or anonymized form. Only "
        "anonymized data may be shared via open data repositories (e.g. zenodo) to "
        "promote open science.</p>",
    ),
    (
        "How can I withdraw from the study?",
        "<p>You may stop participating at any point during the online study by closing "
        "the browser window. If you withdraw before completing the study, your partial "
        "data may be excluded from the main analysis. Since the collected data is "
        "anonymous, it may not be possible to identify and remove your data after the "
        "study has been completed.</p>",
    ),
    (
        "Are there any risks?",
        "<p>This study is considered low risk. You will interact with a word association "
        "game and answer short reflection questions. You may stop at any time if you "
        "feel uncomfortable.</p>",
    ),
)

INFORMATION_SHEET_CONTACT = (
    "If you have any questions about the study, please contact: "
    "Shima Ghasempour, "
    "<a href='mailto:shima.ghasempoour-ardestani@stud.uni-due.de'>"
    "shima.ghasempoour-ardestani@stud.uni-due.de</a>"
)


DEBRIEFING_CONDITION_PLACEHOLDER = "[Static Baseline / Adaptive AI]"
DEBRIEFING_COMPLETION_CODE_PLACEHOLDER = "[COMPLETION_CODE]"

DEBRIEFING_DOCUMENT = """
<section class="debrief-contact">
    <strong>Contact Information:</strong>
    <span>Shima Ghasempour</span>
    <span>Colaps</span>
    <span>Department of Human-centered Computing and Cognitive Science</span>
    <a href="mailto:shima.ghasempoour-ardestani@stud.uni-due.de">shima.ghasempoour-ardestani@stud.uni-due.de</a>
</section>

<section class="debrief-hero">
    <h1>Debriefing</h1>
    <p class="debrief-study-title"><strong>Study:</strong> “Investigating Intersubjective Alignment in Human–AI Collaboration Through a Cooperative Word Association Game”</p>
    <p class="debrief-thanks">Thank you for participating!</p>
</section>

<section class="debrief-introduction">
    <p>The goal of this study was to investigate how humans and AI systems develop shared understanding while collaborating on a cooperative word association game.</p>
    <p>During the game, either the human participant or the AI system acted as the clue-giver, while the other acted as the guesser. By observing how clues were interpreted, we aimed to better understand how shared meaning develops between humans and AI systems.</p>
</section>

<section class="debrief-section">
    <h2>Why is this important?</h2>
    <p>As AI systems become increasingly integrated into education, work, and everyday life, successful collaboration between humans and AI becomes more important. Even when both the human and the AI are working toward the same goal, they may interpret the same information differently.</p>
    <p>Misunderstandings can occur, and successful collaboration often depends on the ability to repair these misunderstandings through feedback and clarification. This study investigates how such shared understanding develops and whether short reflection opportunities can support better communication between humans and AI systems over time.</p>
</section>

<section class="debrief-section">
    <h2>Were there different versions of the game?</h2>
    <p>Yes. Participants were assigned to one of two technical versions of the game:</p>
    <ol>
        <li><strong>Static Baseline:</strong> Reflection responses were collected for analysis but were not used by the AI system during later turns.</li>
        <li><strong>Adaptive AI:</strong> Reflection responses could be incorporated into later AI interactions, allowing the AI system to adapt based on previous communication experiences.</li>
    </ol>
    <p>The game interface was intentionally identical across conditions. Participants were not informed which version they were using during the study to avoid influencing their behaviour.</p>
    <p class="debrief-condition">During this session, you participated in the [Static Baseline / Adaptive AI] condition.</p>
</section>

<section class="debrief-section">
    <h2>What happens to your data?</h2>
    <p>All data has been anonymized and will be used exclusively for research purposes. Anonymized data may be shared via open data repositories (e.g. zenodo) to promote open science.</p>
    <p>The data will contribute to a Master’s thesis at the University of Duisburg-Essen and may also be used in future academic publications or research projects.</p>
    <p>Results will only be reported in aggregated or anonymized form</p>
</section>

<section class="debrief-section debrief-completion-code-section">
    <h2>Your completion code</h2>
    <p>Enter this code on the platform where you found this study (e.g. Amazon Mechanical Turk) to confirm your participation:</p>
    <p class="debrief-completion-code">[COMPLETION_CODE]</p>
</section>

<section class="debrief-section debrief-final-section">
    <h2>Do you have any questions?</h2>
    <p>If you have any questions about this study or would like to learn more about the results, you can contact:</p>
    <p>Shima Ghasempour Ardestani <a href="mailto:shima.ghasempoour-ardestani@stud.uni-due.de">shima.ghasempoour-ardestani@stud.uni-due.de</a></p>
    <p class="debrief-thanks-final">Thank you again for your support!</p>
</section>
"""


def render_debriefing_document(condition, completion_code):
    condition_labels = {
        "baseline": "Static Baseline",
        "adaptive": "Adaptive AI",
    }
    normalized_condition = str(condition or "").strip().lower()
    try:
        condition_label = condition_labels[normalized_condition]
    except KeyError as error:
        raise ValueError("Cannot render debriefing without a valid assigned condition.") from error
    cleaned_completion_code = str(completion_code or "").strip()
    if not cleaned_completion_code:
        raise ValueError("Cannot render debriefing without a completion code.")
    return DEBRIEFING_DOCUMENT.replace(
        DEBRIEFING_CONDITION_PLACEHOLDER,
        condition_label,
    ).replace(
        DEBRIEFING_COMPLETION_CODE_PLACEHOLDER,
        escape(cleaned_completion_code),
    )
