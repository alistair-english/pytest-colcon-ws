#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROMPT_FILE="$SCRIPT_DIR/PROMPT.txt"
STOP_FILE="$SCRIPT_DIR/STOP_LOOP"

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "Error: $PROMPT_FILE not found" >&2
  exit 1
fi

# Clean up any stale stop file from a previous run
if [[ -f "$STOP_FILE" ]]; then
  echo "Removing stale STOP_LOOP file from previous run..."
  rm "$STOP_FILE"
fi

while true; do
  PROMPT=$(<"$PROMPT_FILE")

  if [[ -z "$PROMPT" ]]; then
    echo "Error: $PROMPT_FILE is empty" >&2
    exit 1
  fi

  echo "=== Starting pi run at $(date) ==="
  pi --model openai-codex/gpt-5.5 --thinking high --mode json "$PROMPT" 2>/dev/null | jq --unbuffered -rj '
    if .type == "message_update" then
      .assistantMessageEvent |
      if .type == "text_delta" then .delta
      elif .type == "thinking_delta" then "💭\(.delta)"
      else empty end
    elif .type == "tool_execution_start" then
      "\n🔧 \(.toolName): \(.args | tostring | .[0:200])\n"
    elif .type == "tool_execution_end" then
      if .isError then "❌ Error: \(.result | tostring | .[0:500])\n"
      else "✅ \(.toolName) done\n" end
    elif .type == "agent_end" then
      "\n=== Agent finished ===\n"
    else empty end
  '
  EXIT_CODE=$?
  echo "=== pi exited with code $EXIT_CODE at $(date) ==="

  # Push any commits the agent made
  echo "Pushing commits..."
  git push 2>&1 || echo "⚠️  git push failed (non-fatal)"

  # Check if agent requested a stop
  if [[ -f "$STOP_FILE" ]]; then
    echo ""
    echo "=========================================="
    echo "  AGENT REQUESTED STOP"
    echo "=========================================="
    echo "Reason:"
    cat "$STOP_FILE"
    echo ""
    echo "=========================================="
    echo ""
    echo "To resume, delete AGENT/STOP_LOOP and re-run this script."
    exit 0
  fi

  sleep 1
done
