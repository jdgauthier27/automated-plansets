#!/bin/bash
# Auto-rebuild frontend when JSX/CSS files are edited
for f in $CLAUDE_FILE_PATHS; do
  case "$f" in
    *.jsx|*.tsx|*.css)
      cd "/Users/jdelafontaine/Quebec Solaire/Automated plans/solar_planset_tool/ui"
      npm run build --silent 2>&1 | tail -3
      exit 0
      ;;
  esac
done
