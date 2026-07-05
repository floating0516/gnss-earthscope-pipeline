from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkflowValidatorIntegrationTest(unittest.TestCase):
    def test_production_workflows_validate_normalized_exports(self):
        scripts = [
            ROOT / "scripts" / "workflows" / "run_event_1hz_pride_workflow.sh",
            ROOT / "scripts" / "workflows" / "run_geonet_event_1hz_pride_workflow.sh",
        ]

        for script in scripts:
            with self.subTest(script=script.name):
                text = script.read_text(encoding="utf-8")

                self.assertIn("validate_normalized_export.py", text)
                self.assertIn("normalized_validation_status", text)
                self.assertIn("normalized_export_valid", text)
                self.assertIn('--event-id "$EVENT_ID"', text)
                self.assertIn("--json-out", text)

    def test_production_workflows_derive_machine_readable_failure_reason(self):
        scripts = [
            ROOT / "scripts" / "workflows" / "run_event_1hz_pride_workflow.sh",
            ROOT / "scripts" / "workflows" / "run_geonet_event_1hz_pride_workflow.sh",
        ]

        for script in scripts:
            with self.subTest(script=script.name):
                text = script.read_text(encoding="utf-8")
                self.assertIn("update_workflow_summary_status.py", text)
                self.assertIn("--derive-failure", text)

    def test_geonet_workflow_calls_geonet_normalizer_before_validation(self):
        script = ROOT / "scripts" / "workflows" / "run_geonet_event_1hz_pride_workflow.sh"
        text = script.read_text(encoding="utf-8")

        self.assertIn("normalize_geonet_pride_kin_event.py", text)
        self.assertIn("--workflow-summary", text)
        self.assertIn("--quality-json", text)
        self.assertIn("--normalized-root", text)
        self.assertIn("--db", text)
        self.assertLess(
            text.index("normalize_geonet_pride_kin_event.py"),
            text.index("validate_normalized_export.py"),
        )


if __name__ == "__main__":
    unittest.main()
