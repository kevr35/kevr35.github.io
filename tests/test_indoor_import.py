import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import indoor_import


class IndoorGymRegistryTests(unittest.TestCase):
    def test_add_gym_updates_registry_and_allows_saving_its_climb(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            gyms_path = temporary_path / "gyms.yaml"
            gyms_path.write_text(
                '- name: "Existing Gym"\n  city: "Columbus"\n',
                encoding="utf-8",
            )
            indoor_directory = temporary_path / "indoor"

            with patch.object(indoor_import, "GYMS", gyms_path):
                with patch.object(indoor_import, "INDOOR_CONTENT", indoor_directory):
                    result = indoor_import.add_gym({
                        "name": "New Gym",
                        "city": "Cleveland",
                        "state": "Ohio",
                        "url": "https://example.com/",
                    })
                    saved_path = indoor_import.save_indoor({
                        "filename": "new-gym-v4",
                        "fields": {
                            "gym": "New Gym",
                            "climb_date": "2026-10-14",
                            "grade": "V4",
                            "discipline": "Boulder",
                        },
                    })

            self.assertEqual(result["gym"], "New Gym")
            self.assertEqual(result["gyms"], ["Existing Gym", "New Gym"])
            self.assertIn('  city: "Cleveland"', gyms_path.read_text(encoding="utf-8"))
            self.assertEqual(saved_path, "content/climbing/indoor/new-gym-v4.md")
            self.assertIn('gym: "New Gym"', (indoor_directory / "new-gym-v4.md").read_text(encoding="utf-8"))

    def test_add_gym_rejects_duplicates_and_invalid_websites(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            gyms_path = Path(temporary_directory) / "gyms.yaml"
            gyms_path.write_text('- name: "Existing Gym"\n', encoding="utf-8")

            with patch.object(indoor_import, "GYMS", gyms_path):
                with self.assertRaises(FileExistsError):
                    indoor_import.add_gym({"name": "existing gym"})
                with self.assertRaisesRegex(ValueError, "HTTP or HTTPS"):
                    indoor_import.add_gym({"name": "Another Gym", "url": "javascript:alert(1)"})

            self.assertNotIn("Another Gym", gyms_path.read_text(encoding="utf-8"))

    def test_registry_parser_reports_invalid_quoted_names(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            gyms_path = Path(temporary_directory) / "gyms.yaml"
            gyms_path.write_text('- name: "Incomplete\n', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Invalid quoted name"):
                indoor_import.registry_names(gyms_path)


if __name__ == "__main__":
    unittest.main()
