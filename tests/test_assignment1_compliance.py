import unittest
from pathlib import Path

from src.orchestrator.coordinator import run_war_room


class Assignment1ComplianceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.project_root = Path(__file__).resolve().parent.parent

    def test_decision_outcomes_by_scenario(self) -> None:
        baseline = run_war_room(self.project_root, "baseline")
        optimistic = run_war_room(self.project_root, "optimistic")
        critical = run_war_room(self.project_root, "critical")

        self.assertEqual(baseline["decision"], "Roll Back")
        self.assertEqual(optimistic["decision"], "Proceed")
        self.assertEqual(critical["decision"], "Roll Back")

    def test_required_output_sections_present(self) -> None:
        result = run_war_room(self.project_root, "baseline")
        required_keys = [
            "decision",
            "rationale",
            "risk_register",
            "action_plan_24_48h",
            "communication_plan",
            "confidence_score",
            "what_would_increase_confidence",
        ]
        for key in required_keys:
            self.assertIn(key, result)

    def test_risk_register_quality(self) -> None:
        result = run_war_room(self.project_root, "critical")
        risks = result.get("risk_register", [])
        self.assertGreaterEqual(len(risks), 1)
        for risk in risks:
            self.assertIn("risk", risk)
            self.assertIn("severity", risk)
            self.assertIn("mitigation", risk)
            self.assertNotEqual(risk["mitigation"].strip().lower(), "investigate and mitigate")


if __name__ == "__main__":
    unittest.main()
