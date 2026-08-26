#!/usr/bin/env bash
# Lightweight pre-commit secret check for common secret patterns.
# To use:
# 1. Copy this file to .git/hooks/pre-commit or run: cp pre-commit-checks.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
# 2. Alternatively, enable via: git config core.hooksPath .githooks && mkdir -p .githooks && cp pre-commit-checks.sh .githooks/pre-commit && chmod +x .githooks/pre-commit

set -euo pipefail

STAGED_FILES=$(git diff --cached --name-only --relative)
if [ -z "$STAGED_FILES" ]; then
  exit 0
fi

EXIT_CODE=0
for f in $STAGED_FILES; do
  # Skip binary files
  if file --mime "$f" | grep -q binary; then
    continue
  fi
  if grep -nE "(GOOGLE_API_KEY|AIza[0-9A-Za-z_-]{35}|-----BEGIN PRIVATE KEY-----|PRIVATE_KEY=|AKIA[0-9A-Z]{16})" "$f" >/dev/null 2>&1; then
    echo "Potential secret found in staged file: $f"
    grep -nE "(GOOGLE_API_KEY|-----BEGIN PRIVATE KEY-----|PRIVATE_KEY=|AKIA[0-9A-Z]{16})" "$f" || true
    EXIT_CODE=2
  fi
  if [[ "$f" =~ \.env$ || "$f" =~ \.env\.local$ || "$f" =~ \.env\.development$ ]]; then
    echo "Refusing to commit environment file: $f"
    EXIT_CODE=2
  fi
done

if [ $EXIT_CODE -ne 0 ]; then
  echo "Commit aborted by pre-commit secret check. Inspect the staged files and remove secrets." >&2
  exit $EXIT_CODE
fi

exit 0
