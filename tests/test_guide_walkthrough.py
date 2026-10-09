import html
import re
import unittest

from core.constants import BOARD_SIZE, BOMB_COUNT, TARGET_COUNT
from core.tutorial import TUTORIAL_BOARD, TUTORIAL_ROUND_2_BOARD
from core.words import ROUND_BOARDS
from ui import guide_walkthrough as gw


def _shown_words(text):
    plain = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return {word.lower() for word in re.findall(r"[A-Za-z]+", plain)}


def _rendered_parts():
    for role, title, parts in gw.GUIDE_WALKTHROUGH_SLIDES:
        yield title, title
        for part in parts:
            yield title, part() if callable(part) else part


class GuideWalkthroughTests(unittest.TestCase):
    def test_no_step_shows_a_real_board_word(self):
        """Titles, texts, cards, clues, labels and captions: nothing in the
        walkthrough may be a card from a real board."""
        board_words = {
            word.lower()
            for board in ROUND_BOARDS.values()
            for role in ("target", "neutral", "bomb")
            for word, _ in board[role]
        }
        shown = set()
        for _title, text in _rendered_parts():
            shown |= _shown_words(text)
        self.assertEqual(shown & board_words, set())

    def test_example_boards_are_not_the_practice_boards(self):
        practice = {w.lower() for w in TUTORIAL_BOARD + TUTORIAL_ROUND_2_BOARD}
        for board in (gw.GUESSER_BOARD, gw.CLUE_GIVER_BOARD):
            self.assertEqual({w.lower() for w, _ in board} & practice, set())

    def test_example_boards_follow_the_real_board_layout(self):
        for board in (gw.GUESSER_BOARD, gw.CLUE_GIVER_BOARD):
            roles = [role for _, role in board]
            self.assertEqual(len(board), BOARD_SIZE)
            self.assertEqual(len({w for w, _ in board}), BOARD_SIZE)
            self.assertEqual(roles.count("target"), TARGET_COUNT)
            self.assertEqual(roles.count("bomb"), BOMB_COUNT)

    def test_clue_giver_example_matches_what_the_steps_say(self):
        roles = dict(gw.CLUE_GIVER_BOARD)
        words = {w.lower() for w in roles}
        self.assertNotIn(gw.CLUE_GIVER_CLUE[0], words)
        self.assertEqual(len(gw.CLUE_GIVER_INTENDED), gw.CLUE_GIVER_CLUE[1])
        self.assertTrue(all(roles[w] == "target" for w in gw.CLUE_GIVER_INTENDED))
        # Step 3 explains that a prediction can differ from the intended cards.
        self.assertEqual(len(gw.CLUE_GIVER_PREDICTED), gw.CLUE_GIVER_CLUE[1])
        self.assertNotEqual(set(gw.CLUE_GIVER_PREDICTED), set(gw.CLUE_GIVER_INTENDED))
        self.assertTrue(all(w in roles for w in gw.CLUE_GIVER_PREDICTED))
        # "The AI chose ... just as the player predicted": first pick +2, second neutral.
        self.assertEqual(gw.CLUE_GIVER_AI_PICKS, gw.CLUE_GIVER_PREDICTED)
        hit, miss = gw.CLUE_GIVER_AI_PICKS
        self.assertIn(hit, gw.CLUE_GIVER_INTENDED)
        self.assertEqual(roles[miss], "neutral")
        # The good general-link example names no card; the bad one does.
        self.assertEqual(_shown_words(gw.CLUE_GIVER_LINK) & words, set())
        self.assertTrue(_shown_words(gw.CLUE_GIVER_BAD_LINK) & words)

    def test_guesser_example_matches_what_the_steps_say(self):
        roles = dict(gw.GUESSER_BOARD)
        words = {w.lower() for w in roles}
        self.assertNotIn(gw.GUESSER_CLUE[0], words)
        self.assertEqual(len(gw.GUESSER_INTENDED), gw.GUESSER_CLUE[1])
        self.assertTrue(all(roles[w] == "target" for w in gw.GUESSER_INTENDED))
        hit, miss = gw.GUESSER_PICKS
        self.assertIn(hit, gw.GUESSER_INTENDED)
        self.assertEqual(roles[miss], "neutral")
        self.assertEqual(_shown_words(gw.GUESSER_RATIONALE) & words, set())

    def test_intended_cards_and_prediction_look_different(self):
        intended = gw.fig_clue_step2()
        predicted = gw.fig_clue_step3()
        for word in gw.CLUE_GIVER_INTENDED:
            self.assertIn(f'class="guide-walk-chip on">&#10003; {word}<', intended)
        for word in gw.CLUE_GIVER_PREDICTED:
            self.assertIn(f">{word}<span class=\"guide-walk-tag-x\">", predicted)
        self.assertNotIn("guide-walk-chip", predicted)
        self.assertNotIn("guide-walk-tag", intended)

    def test_every_picture_is_a_single_html_line(self):
        # An indented blank line inside st.markdown would start a Markdown
        # code block and print the rest of the picture as text.
        for title, parts in ((t, p) for _r, t, p in gw.GUIDE_WALKTHROUGH_SLIDES):
            for part in parts:
                if callable(part):
                    out = part()
                    self.assertNotIn("\n", out, title)
                    self.assertIn("<figure", out, title)


if __name__ == "__main__":
    unittest.main()
