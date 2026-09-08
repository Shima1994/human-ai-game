import unittest
from pathlib import Path

from ui.study_documents import (
    DEBRIEFING_CONDITION_PLACEHOLDER,
    render_debriefing_document,
)


BASELINE_SENTENCE = (
    "During this session, you participated in the Static Baseline condition."
)
ADAPTIVE_SENTENCE = (
    "During this session, you participated in the Adaptive AI condition."
)


class DebriefingTests(unittest.TestCase):
    def test_baseline_disclosure_sentence(self):
        rendered = render_debriefing_document("baseline")
        self.assertIn(BASELINE_SENTENCE, rendered)
        self.assertNotIn(DEBRIEFING_CONDITION_PLACEHOLDER, rendered)

    def test_adaptive_disclosure_sentence(self):
        rendered = render_debriefing_document("adaptive")
        self.assertIn(ADAPTIVE_SENTENCE, rendered)
        self.assertNotIn(DEBRIEFING_CONDITION_PLACEHOLDER, rendered)

    def test_both_conditions_use_the_same_ui_and_only_condition_text_differs(self):
        baseline = render_debriefing_document("baseline")
        adaptive = render_debriefing_document("adaptive")
        self.assertEqual(
            baseline.replace(BASELINE_SENTENCE, "ASSIGNED_CONDITION"),
            adaptive.replace(ADAPTIVE_SENTENCE, "ASSIGNED_CONDITION"),
        )
        for class_name in (
            "debrief-contact",
            "debrief-hero",
            "debrief-introduction",
            "debrief-section",
            "debrief-condition",
        ):
            self.assertIn(class_name, baseline)
            self.assertIn(class_name, adaptive)

    def test_approved_document_content_is_complete(self):
        rendered = render_debriefing_document("baseline")
        required_text = (
            "Contact Information:",
            "Shima Ghasempour",
            "Thank you for participating!",
            "Why is this important?",
            "Were there different versions of the game?",
            "Static Baseline:",
            "Adaptive AI:",
            "What happens to your data?",
            "Results will only be reported in aggregated or anonymized form",
            "Do you have any questions?",
            "Shima Ghasempour Ardestani",
            "Thank you again for your support!",
        )
        for text in required_text:
            self.assertIn(text, rendered)

    def test_invalid_condition_cannot_expose_placeholder(self):
        with self.assertRaises(ValueError):
            render_debriefing_document("unassigned")

    def test_runtime_uses_canonical_session_condition_after_questionnaire(self):
        source = Path("ui/screens.py").read_text(encoding="utf-8-sig")
        questionnaire_gate = source.index(
            'if not st.session_state.get("post_game_questionnaire_submitted")'
        )
        debriefing_gate = source.index(
            'if not st.session_state.get("debriefing_acknowledged")'
        )
        condition_render = source.index(
            'render_debriefing_document(st.session_state.get("condition"))'
        )
        self.assertLess(questionnaire_gate, debriefing_gate)
        self.assertLess(debriefing_gate, condition_render)


if __name__ == "__main__":
    unittest.main()
