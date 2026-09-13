"""Pytest runner for headless browser tests covering storefront recovery, layout, navigation, and zoom."""
import subprocess
import shutil
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_storefront_browser_coverage():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js runtime not found on host")

    script = ROOT / "tests" / "test_storefront_browser.cjs"
    assert script.exists(), f"Test script {script} missing"

    result = subprocess.run(
        [node, str(script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=35,
    )
    assert result.returncode == 0, f"Browser test failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert "PASS: " in result.stdout
    assert "storefront browser coverage checks" in result.stdout
