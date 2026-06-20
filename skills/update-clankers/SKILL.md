---
name: update-clankers
description: This skill should be used when the user asks to "update my clankers", "update my clanker", "update my AI agents", "update my coding agents", "update claude and cursor", or invokes /update-clankers. Detects which AI coding CLI agents are installed on PATH (claude, cursor-agent, opencode, codex, pi) and runs each one's update command in parallel.
---

# Update Clankers

Update the user's installed AI coding CLIs in one shot.

## Agents and their update commands

| Agent          | Update command                              |
| -------------- | ------------------------------------------- |
| `claude`       | `claude update`                             |
| `cursor-agent` | `cursor-agent update`                       |
| `opencode`     | `opencode upgrade`                          |
| `codex`        | `npm install -g @openai/codex@latest`       |
| `pi`           | `pi update --self`                          |

## Procedure

1. Prefer running the bundled script from this skill directory:

   ```bash
   ./scripts/update-clankers.sh
   ```

   The script detects installed agents, runs update commands in parallel, and prints a compact per-agent summary.
2. If running manually, detect installed agents with a single Bash call: `command -v claude cursor-agent opencode codex pi`. Only the ones that resolve are candidates.
3. For each detected agent, start its update command as a background Bash call (`run_in_background: true`). Issue all background calls in a single message so they run in parallel.
4. When all background tasks complete, report per-agent status as a compact summary: updated to new version, already latest, or failed (include the failing line of output).
5. Skip agents that are not on PATH — do not install them, do not prompt.

## Notes

- Claude Code and Cursor Agent auto-update in the background; `claude update` / `cursor-agent update` just force an immediate check.
- OpenCode's subcommand is `upgrade`, not `update`.
- Codex has no built-in update subcommand; npm is the mechanism. If `which codex` resolves inside a Homebrew prefix (contains `/Cellar/` or `/opt/homebrew/`), use `brew upgrade --cask codex` instead.
- Pi's self-update command is `pi update --self`; `pi update` also updates installed Pi packages/extensions.
