import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the project root to sys.path so we can import kronos
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from kronos.engine.plot_manager import parse_plot_manifest

class KronosSmokeTest(unittest.TestCase):
    """Headless smoke tests for Kronos IDE engine components."""

    def test_parse_plot_manifest_empty(self):
        """Test parse_plot_manifest handles non-existent files gracefully."""
        items = parse_plot_manifest(Path("/tmp/nonexistent_manifest_file.json"))
        self.assertEqual(items, [])

    def test_parse_plot_manifest_valid(self):
        """Test parse_plot_manifest logic with mock JSON data."""
        import json
        import tempfile
        
        test_data = {
            "ok": True,
            "figures": [
                {
                    "num": 1,
                    "var": None,
                    "title": "Test Fig",
                    "png": "/tmp/fig_0.png",
                    "axes": [
                        {"index": 0, "title": "Subplot A", "bbox": [0.1, 0.1, 0.9, 0.9]},
                    ],
                },
            ],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
            json.dump(test_data, tf)
            tf_path = Path(tf.name)
            
        try:
            items = parse_plot_manifest(tf_path)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["title"], "Subplot A")
            self.assertEqual(items[0]["axes_index"], 0)
        finally:
            tf_path.unlink()

if __name__ == "__main__":
    unittest.main()
