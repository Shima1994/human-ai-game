import unittest

from ui.study_documents import (
    DEBRIEFING_COMPLETION_CODE_PLACEHOLDER,
    DEBRIEFING_CONDITION_PLACEHOLDER,
    render_debriefing_document,
)


BASELINE_SENTENCE = (
    "During this session, you participated in the Static Baseline condition."
)
ADAPTIVE_SENTENCE = (
    "During this session, you participated in the Adaptive AI condition."
)
SAMPLE_COMPLETION_CODE = "ABCD1234"


class DebriefingTests(unittest.TestCase):
    def test_baseline_disclosure_sentence(self):
        rendered = render_debriefing_document("baseline", SAMPLE_COMPLETION_CODE)
        self.assertIn(BASELINE_SENTENCE, rendered)
        self.assertNotIn(DEBRIEFING_CONDITION_PLACEHOLDER, rendered)

    def test_adaptive_disclosure_sentence(self):
        rendered = render_debriefing_document("adaptive", SAMPLE_COMPLETION_CODE)
        self.assertIn(ADAPTIVE_SENTENCE, rendered)
        self.assertNotIn(DEBRIEFING_CONDITION_PLACEHOLDER, rendered)

    def test_both_conditions_use_the_same_ui_and_only_condition_text_differs(self):
        baseline = render_debriefing_document("baseline", SAMPLE_COMPLETION_CODE)
        adaptive = render_debriefing_document("adaptive", SAMPLE_COMPLETION_CODE)
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
            "debrief-completion-code-section",
            "debrief-completion-code",
        ):
            self.assertIn(class_name, baseline)
            self.assertIn(class_name, adaptive)

    def test_approved_document_content_is_complete(self):
        rendered = render_debriefing_document("baseline", SAMPLE_COMPLETION_CODE)
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
            "Your completion code",
            "Do you have any questions?",
            "Shima Ghasempour Ardestani",
            "Thank you again for your support!",
        )
        for text in required_text:
            self.assertIn(text, rendered)

    def test_completion_code_is_rendered_and_escaped(self):
        rendered = render_debriefing_document("baseline", SAMPLE_COMPLETION_CODE)
        self.assertIn(SAMPLE_COMPLETION_CODE, rendered)
        self.assertNotIn(DEBRIEFING_COMPLETION_CODE_PLACEHOLDER, rendered)

        unsafe_rendered = render_debriefing_document("baseline", "<script>bad</script>")
        self.assertNotIn("<script>bad</script>", unsafe_rendered)
        self.assertIn("&lt;script&gt;", unsafe_rendered)

    def test_invalid_condition_cannot_expose_placeholder(self):
        with self.assertRaises(ValueError):
            render_debriefing_document("unassigned", SAMPLE_COMPLETION_CODE)

    def test_missing_completion_code_is_rejected(self):
        with self.assertRaises(ValueError):
            render_debriefing_document("baseline", "")
        with self.assertRaises(ValueError):
            render_debriefing_document("baseline", None)


if __name__ == "__main__":
    unittest.main()
