import ast
import unittest
from pathlib import Path

from ui.game_guide import (
    CLUE_GIVER_INTRO,
    CLUE_GIVER_OUTRO,
    CLUE_GIVER_STEPS,
    GUIDE_NO_AI_TOOLS,
    GUIDE_OVERVIEW,
    GUIDE_REMINDERS,
    GUIDE_ROLE,
    GUIDE_SECTIONS,
)


class GameGuideTests(unittest.TestCase):
    def test_all_eleven_visual_sections_are_present(self):
        self.assertEqual(len(CLUE_GIVER_STEPS), 6)
        self.assertEqual(len(GUIDE_SECTIONS), 8)
        titles = [title for title, _ in GUIDE_SECTIONS]
        self.assertEqual(
            titles,
            [
                "Targets, Neutral Cards, and Bombs",
                "When the AI Is the Clue-Giver",
                "Try to Connect More Than One Target",
                "Interactions and Round Limit",
                "Skipping",
                "Time Limit",
                "After an Interaction",
                "Scoring, Stars, and Medals",
            ],
        )
        # Shown on its own above section 1 instead (see screen_welcome).
        self.assertEqual(GUIDE_NO_AI_TOOLS[0], "Play on Your Own: No AI Tools")
        # Communicative Repair was deliberately removed -- purely theoretical
        # framing that shouldn't be surfaced to participants (should come
        # naturally rather than being explained up front).
        self.assertNotIn("Communicative Repair", titles)

    def test_six_clue_giver_steps_are_in_required_order(self):
        self.assertEqual(
            [heading for heading, _ in CLUE_GIVER_STEPS],
            [
                "Give a one-word clue",
                "Choose the clue number",
                "Select your intended target cards",
                "Predict what the AI will choose",
                "Rate your expected shared understanding",
                "Briefly explain the general connection",
            ],
        )

    def test_required_instructional_content_is_complete(self):
        content = "\n".join(
            [GUIDE_OVERVIEW, GUIDE_ROLE, CLUE_GIVER_INTRO]
            + [heading + "\n" + body for heading, body in CLUE_GIVER_STEPS]
            + [CLUE_GIVER_OUTRO]
            + [heading + "\n" + body for heading, body in GUIDE_SECTIONS]
            + ["\n".join(GUIDE_NO_AI_TOOLS)]
            + [GUIDE_REMINDERS]
        )
        required_phrases = (
            "You and the AI are on the same team.",
            "5 target cards",
            "9 neutral cards",
            "2 bomb cards",
            "Give a one-word clue",
            "Choose the clue number",
            "Select your intended target cards",
            "Predict what the AI will choose",
            "Rate your expected shared understanding",
            "Briefly explain the general connection",
            "When the AI Is the Clue-Giver",
            "Try to Connect More Than One Target",
            "maximum of 3 completed interactions",
            "Skip option up to 2 times",
            "90 seconds as a Guesser",
            "120 seconds to give a clue",
            "it will consume one of your skip",
            "30 seconds to make your guess",
            "except for the first time when this happens",
            "After an Interaction",
            "2 points when the guesser selects the card the clue-giver had in mind",
            "1 point for another valid target card",
            "earn a star",
            "final medal",
            "MOST IMPORTANT THINGS TO REMEMBER",
            "the History panel on the left shows the clues, guesses and results",
            "Please play this game on your own.",
            "Pasting text into the game is disabled.",
        )
        content += "\nMOST IMPORTANT THINGS TO REMEMBER"
        for phrase in required_phrases:
            self.assertIn(phrase, content)

    def test_screen_uses_expected_progressive_disclosure_and_navigation(self):
        source = Path("ui/screens.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(source)

        def function_source(name):
            node = next(
                node
                for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == name
            )
            return ast.get_source_segment(source, node)

        screen_source = function_source("screen_welcome")
        rules_source = function_source("_render_written_guide")
        # The no-AI notice comes first, then the visual walkthrough and the
        # full written rules as two tabs; Continue only unlocks once the
        # walkthrough's last step has been reached.
        self.assertLess(
            screen_source.index('key="guide_no_ai_notice"'),
            screen_source.index("st.tabs("),
        )
        self.assertIn("render_guide_walkthrough()", screen_source)
        self.assertIn("_render_written_guide()", screen_source)
        self.assertIn("disabled=not walkthrough_done", screen_source)
        self.assertIn("st.session_state.started = True", screen_source)

        self.assertIn('"**1**　Overview", expanded=True', rules_source)
        self.assertIn('"**2**　Your Role", expanded=True', rules_source)
        self.assertIn('"**4**　When You Are the Clue-Giver"', rules_source)
        self.assertIn("render_guide_section(3, cards_title", rules_source)
        self.assertIn("zip(later_sections, section_icons[1:]), start=5", rules_source)
        self.assertIn("expanded=False", rules_source)

    def test_role_section_shows_the_in_game_role_badges(self):
        from ui.components import ROLE_BADGE_LABELS
        from ui.screens import _guide_role_with_badges

        rendered = _guide_role_with_badges()
        self.assertIn('role-badge role-clue', rendered)
        self.assertIn('role-badge role-guess', rendered)
        self.assertIn("You&#x27;re giving the clue", rendered)
        self.assertIn(ROLE_BADGE_LABELS["guess"], rendered)
        # The guide text itself is unchanged; badges are added only on render.
        self.assertIn("- Clue-Giver\n", GUIDE_ROLE)
        self.assertIn("The AI takes the other role.", rendered)

    def test_every_guide_figure_belongs_to_an_existing_section(self):
        from ui.components import GUIDE_SECTION_FIGURES

        titles = {title for title, _ in GUIDE_SECTIONS}
        from ui.components import GUIDE_STEP_FIGURES

        self.assertEqual(
            set(GUIDE_SECTION_FIGURES),
            {
                "When the AI Is the Clue-Giver",
                "Targets, Neutral Cards, and Bombs",
                "Interactions and Round Limit",
                "Skipping",
                "Time Limit",
                "Scoring, Stars, and Medals",
            },
        )
        self.assertTrue(set(GUIDE_SECTION_FIGURES) <= titles)
        step_headings = {heading for heading, _ in CLUE_GIVER_STEPS}
        self.assertTrue(set(GUIDE_STEP_FIGURES) <= step_headings)
        for figure in list(GUIDE_SECTION_FIGURES.values()) + list(GUIDE_STEP_FIGURES.values()):
            html = figure()
            self.assertTrue(html.startswith('<figure class="guide-figure">'))
            # One line: an indented blank line would turn the rest into a
            # Markdown code block.
            self.assertNotIn("\n", html)

    def test_guide_figure_numbers_match_the_game_rules(self):
        from core.constants import (
            CLUE_GIVER_TIMER_SECONDS,
            FINAL_GUESS_TIMER_SECONDS,
            GUESSER_TIMER_SECONDS,
            MAX_POSSIBLE_SESSION_SCORE,
        )
        from ui.components import guide_scoring_figure, guide_timers_figure

        def mmss(seconds):
            return f"{seconds // 60:02d}:{seconds % 60:02d}"

        timers = guide_timers_figure()
        for seconds in (GUESSER_TIMER_SECONDS, CLUE_GIVER_TIMER_SECONDS, FINAL_GUESS_TIMER_SECONDS):
            self.assertIn(mmss(seconds), timers)
        scoring = guide_scoring_figure()
        for text in ("+2", "+1", "10+", "20+", "30+", f"{MAX_POSSIBLE_SESSION_SCORE} points"):
            self.assertIn(text, scoring)

    def test_guide_figures_never_show_a_real_board_word(self):
        """No word anywhere in a guide figure (cards, clues, labels or
        captions) may be a card on one of the real boards, so the guide
        can't hint at any real target, neutral or bomb."""
        import html
        import re

        from core.words import ROUND_BOARDS
        from ui.components import GUIDE_SECTION_FIGURES, GUIDE_STEP_FIGURES
        from ui.screens import _guide_role_with_badges

        board_words = {
            word.lower()
            for board in ROUND_BOARDS.values()
            for role in ("target", "neutral", "bomb")
            for word, _ in board[role]
        }
        figures = [
            figure()
            for figure in list(GUIDE_SECTION_FIGURES.values()) + list(GUIDE_STEP_FIGURES.values())
        ] + [_guide_role_with_badges()]
        shown = {
            word.lower()
            for figure in figures
            for word in re.findall(r"[A-Za-z]+", html.unescape(re.sub(r"<[^>]+>", " ", figure)))
        }
        self.assertEqual(shown & board_words, set())

    def test_each_guide_section_has_a_distinct_material_icon(self):
        source = Path("ui/screens.py").read_text(encoding="utf-8-sig")
        icons = (
            ":material/groups:",
            ":material/switch_account:",
            ":material/lightbulb:",
            ":material/smart_toy:",
            ":material/target:",
            ":material/style:",
            ":material/sync:",
            ":material/skip_next:",
            ":material/schedule:",
            ":material/rate_review:",
            ":material/block:",
            ":material/emoji_events:",
        )
        for icon in icons:
            self.assertIn(icon, source)


if __name__ == "__main__":
    unittest.main()
