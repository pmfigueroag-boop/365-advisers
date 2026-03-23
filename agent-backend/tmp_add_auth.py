"""
Add auth dependency to all route modules.

Strategy:
  1. Read the file as a string
  2. Add auth import AFTER the docstring and before the first code
  3. Modify the `router = APIRouter(...)` line to include dependencies
  4. Ensure `Depends` is in the fastapi import
"""

import os
import re

ROUTES_DIR = r"C:\Users\pmfig\.gemini\antigravity\scratch\365-advisers\agent-backend\src\routes"
SKIP = {"__init__.py", "auth.py", "health.py"}
AUTH_IMPORT = "from src.auth.dependencies import get_current_user\n"

modified = []
errors = []

for fname in sorted(os.listdir(ROUTES_DIR)):
    if not fname.endswith(".py") or fname in SKIP:
        continue

    path = os.path.join(ROUTES_DIR, fname)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if "get_current_user" in content:
        continue

    original = content

    # Step 1: Ensure Depends is in the fastapi import
    if "Depends" not in content:
        content = re.sub(
            r"from fastapi import (APIRouter)",
            r"from fastapi import APIRouter, Depends",
            content,
            count=1,
        )

    # Step 2: Add auth import.
    # Strategy: insert it right before the `router = ` line
    router_match = re.search(r'^(router\s*=\s*APIRouter)', content, re.MULTILINE)
    if router_match:
        pos = router_match.start()
        content = content[:pos] + AUTH_IMPORT + "\n" + content[pos:]

    # Step 3: Add dependencies to router = APIRouter(...)
    # Handle both single-line and multi-line router definitions
    # Find the full router = APIRouter(...) statement
    router_pattern = re.compile(
        r'(router\s*=\s*APIRouter\()([^)]*)\)',
        re.DOTALL,
    )
    match = router_pattern.search(content)
    if match and "dependencies" not in match.group(0):
        inner = match.group(2).rstrip()
        if inner.endswith(","):
            new_inner = inner + " dependencies=[Depends(get_current_user)]"
        else:
            new_inner = inner + ", dependencies=[Depends(get_current_user)]"
        replacement = match.group(1) + new_inner + ")"
        content = content[:match.start()] + replacement + content[match.end():]

    # Verify syntax
    try:
        compile(content, fname, "exec")
    except SyntaxError as e:
        errors.append(f"{fname}: line {e.lineno}: {e.msg}")
        continue  # Don't write broken files

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    modified.append(fname)

print(f"Modified: {len(modified)} files")
print(f"Errors (not written): {len(errors)}")
for e in errors:
    print(f"  ✗ {e}")
for f in modified[:10]:
    print(f"  ✓ {f}")
if len(modified) > 10:
    print(f"  ... and {len(modified) - 10} more")
