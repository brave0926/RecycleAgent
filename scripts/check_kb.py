"""Quick check that guidelines.md loads: prints size, token estimate and headings."""
import sys
from pathlib import Path

# Windows consoles may not default to UTF-8, which would break Korean output.
sys.stdout.reconfigure(encoding="utf-8")

text = (Path(__file__).resolve().parent.parent / "data" / "guidelines.md").read_text(encoding="utf-8")

print(f"Characters: {len(text):,}")
print(f"Estimated tokens (chars / 2): {len(text) // 2:,}")
print("\nHeadings:")
for line in text.splitlines():
    if line.startswith("### "):
        print(f"    {line}")
    elif line.startswith("## "):
        print(line)
