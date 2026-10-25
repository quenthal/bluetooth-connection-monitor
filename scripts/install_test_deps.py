"""Print the requirements of the Home Assistant integrations the tests import.

Usage: pip install $(python scripts/install_test_deps.py)
"""

from importlib import resources
import json

for integration in ("bluetooth", "usb"):
    manifest = (
        resources.files("homeassistant.components") / integration / "manifest.json"
    )
    print(*json.loads(manifest.read_text(encoding="utf-8"))["requirements"], sep="\n")
