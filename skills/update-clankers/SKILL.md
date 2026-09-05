---
name: update-clankers
description: Update installed AI coding CLIs (Claude, Copilot, Cursor Agent, OpenCode, Codex, Pi). Use when asked to "update my clankers", "update my AI agents", or /update-clankers.
compatibility: Linux, macOS, Windows; Python 3.10+.
---

# Update Clankers

1. Resolve `scripts/update-clankers.py` relative to **this skill's directory**, not the project. Use its quoted absolute path.
2. **Run it**, using an existing Python 3.10+ interpreter:
   - Linux/macOS: `python3 "<skill-dir>/scripts/update-clankers.py"`
   - Windows: `py -3 "<skill-dir>\scripts\update-clankers.py"` (or `python`).
3. **Wait until it exits.** Allow up to ten minutes per agent. If your tool returns a job handle, keep waiting on that job; don't launch a duplicate.
4. Summarize its results: updated, checked (version unchanged), skipped, or failed. Nonzero exit means incomplete. Never infer “already latest” from unchanged output.

The script detects the active installation's owner, selects the updater, and verifies versions. Don't substitute guessed commands or install missing agents.

Only use `--dry-run` for inspection requests. `--agent codex` limits the run. Missing Python or a failed update? Read [troubleshooting](references/troubleshooting.md) **only then**. Do not silently install prerequisites, elevate permissions, or switch installers.
