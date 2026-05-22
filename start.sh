#!/usr/bin/env bash
# Start the MTG Sideboard Manager webapp
# Usage: ./start.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"

# Use local venv if present, otherwise fall back to system python
if [ -d "$VENV" ]; then
  PYTHON="$VENV/bin/python"
  UVICORN="$VENV/bin/uvicorn"
else
  PYTHON="python3"
  UVICORN="uvicorn"
fi

cd "$SCRIPT_DIR"

# Create data dir if missing
mkdir -p data

# Bootstrap empty data files if not present
for f in meta_decks.json my_decks.json sideboards.json; do
  if [ ! -f "data/$f" ]; then
    case "$f" in
      meta_decks.json) echo '{"last_fetched":null,"meta_id":null,"decks":[]}' > "data/$f" ;;
      my_decks.json) echo '{"folder_url":"https://archidekt.com/folders/1123156","last_folder_sync":null,"decks":[]}' > "data/$f" ;;
      sideboards.json) echo '{"plans":{},"theoretical_pool":{}}' > "data/$f" ;;
    esac
    echo "Created data/$f"
  fi
done

echo "Starting MTG Sideboard Manager at http://localhost:8000"
$UVICORN main:app --host 0.0.0.0 --port 8000 --reload
