#!/usr/bin/env bash
set -u

agents=(claude copilot cursor-agent opencode codex pi)
commands=(
  "claude update"
  "copilot update"
  "cursor-agent update"
  "opencode upgrade"
  "npm install -g @openai/codex@latest"
  "pi update --self"
)

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT

pids=()
names=()

for i in "${!agents[@]}"; do
  agent="${agents[$i]}"
  path="$(command -v "$agent" 2>/dev/null || true)"
  if [[ -z "$path" ]]; then
    printf '%-12s skipped (not on PATH)\n' "$agent"
    continue
  fi

  command_to_run="${commands[$i]}"

  if [[ "$agent" == "codex" && ( "$path" == *"/Cellar/"* || "$path" == *"/opt/homebrew/"* ) ]]; then
    command_to_run="brew upgrade --cask codex"
  fi

  log_file="$workdir/$agent.log"
  (
    printf '$ %s\n' "$command_to_run"
    bash -c "$command_to_run"
  ) >"$log_file" 2>&1 &

  pids+=("$!")
  names+=("$agent")
  printf '%-12s started: %s\n' "$agent" "$command_to_run"
done

if [[ "${#pids[@]}" -eq 0 ]]; then
  echo "No supported AI coding CLIs found on PATH."
  exit 0
fi

echo
status=0
for i in "${!pids[@]}"; do
  pid="${pids[$i]}"
  agent="${names[$i]}"
  log_file="$workdir/$agent.log"

  if wait "$pid"; then
    summary="$(grep -Eim1 'updated|already|latest|up to date|success|installed|changed|added|removed|upgraded|current' "$log_file" || true)"
    if [[ -z "$summary" ]]; then
      summary="completed"
    fi
    printf '%-12s ok: %s\n' "$agent" "$summary"
  else
    status=1
    summary="$(grep -Eim1 'error|failed|ERR!|permission|denied|not found|cannot|unable' "$log_file" || tail -n 1 "$log_file")"
    printf '%-12s failed: %s\n' "$agent" "$summary"
    sed 's/^/  /' "$log_file"
  fi
done

exit "$status"
