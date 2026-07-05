#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

find "$ROOT/scripts" "$ROOT/tools" -name "*.sh" -print0 | while IFS= read -r -d '' file; do
  bash -n "$file"
done

echo "shell_syntax_ok"
