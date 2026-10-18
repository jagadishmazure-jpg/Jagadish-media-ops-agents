"""Print the real test total (never rely on -qq swallowing it)."""

import subprocess
import sys

out = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q"],
    capture_output=True, text=True, cwd=__file__.rsplit("/", 2)[0],
)
tests = [ln for ln in out.stdout.splitlines()
         if "::" in ln and not ln.startswith("=")]
print(f"{len(tests)} tests collected")
