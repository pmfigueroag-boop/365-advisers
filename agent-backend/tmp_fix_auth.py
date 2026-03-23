"""
Fix misplaced auth imports in route files.

The batch script inserted the auth import line after the "last import line",
but that was wrong when a multi-line import (using parentheses) was the last import.
This script:
  1. Removes the misplaced auth import line
  2. Re-inserts it after the REAL last import statement (after closing paren)
"""

import os
import re

ROUTES_DIR = r"C:\Users\pmfig\.gemini\antigravity\scratch\365-advisers\agent-backend\src\routes"
SKIP = {"__init__.py", "auth.py", "health.py"}
AUTH_LINE = "from src.auth.dependencies import get_current_user"

fixed = 0
ok = 0

for fname in sorted(os.listdir(ROUTES_DIR)):
    if not fname.endswith(".py") or fname in SKIP:
        continue

    path = os.path.join(ROUTES_DIR, fname)
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find auth import line(s)
    auth_indices = [i for i, line in enumerate(lines) if AUTH_LINE in line]
    if not auth_indices:
        continue

    # Remove all auth import lines
    clean_lines = [line for i, line in enumerate(lines) if i not in auth_indices]

    # Find the correct insertion point: after the last top-level import block
    # We need to handle multi-line imports (parenthesized)
    in_paren = 0
    last_import_end = 0

    for i, line in enumerate(clean_lines):
        stripped = line.strip()

        # Track parentheses
        in_paren += stripped.count("(") - stripped.count(")")

        # If we're inside a multi-line import, skip
        if in_paren > 0:
            continue

        # Check if this is an import line (or the end of one)
        if stripped.startswith("from ") or stripped.startswith("import "):
            last_import_end = i
        elif stripped == ")" and i > 0:
            # Closing paren of multi-line import
            last_import_end = i

    # Insert auth import after last_import_end
    clean_lines.insert(last_import_end + 1, AUTH_LINE + "\n")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(clean_lines)

    # Verify syntax
    try:
        compile("".join(clean_lines), fname, "exec")
        ok += 1
    except SyntaxError as e:
        fixed += 1
        print(f"  SYNTAX ERROR in {fname}: {e}")

print(f"Processed: {ok + fixed} files ({ok} ok, {fixed} with errors)")
