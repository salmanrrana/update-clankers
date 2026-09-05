# update-clankers

A cross-harness skill / Claude Code plugin that updates your installed AI coding CLIs: **Claude, Copilot, Cursor Agent, OpenCode, Codex, and Pi**.

It identifies the active installation before choosing an updater, waits for completion, and checks the version afterward. No more updating an unused npm copy of a Homebrew-installed Codex and calling it success.

## Install

```bash
npx skills add salmanrrana/update-clankers
```

Then ask your agent to **“update my clankers.”** The short skill entry point runs the script; troubleshooting details load only on failure. Requires **Python 3.10+**, with no third-party Python packages. Supports Linux, macOS, and native Windows; WSL updates the Linux installations visible inside WSL, not Windows installations.

## Run directly

From this repository:

```bash
# Inspect versions, executable paths, and update commands without updating
python3 skills/update-clankers/scripts/update-clankers.py --dry-run

# Update all installed agents
python3 skills/update-clankers/scripts/update-clankers.py

# Update only Codex
python3 skills/update-clankers/scripts/update-clankers.py --agent codex
```

On Windows, use `py -3` or a Python 3.10+ `python` instead of `python3`. The Bash entry point remains available:

```bash
bash skills/update-clankers/scripts/update-clankers.sh --dry-run
```

When running from another directory, use the script's **absolute path**.

## Installer support

| Installation | Update behavior |
| --- | --- |
| npm, including nvm prefixes | Match the active executable to the global package; install and verify the registry's exact `latest` version |
| pnpm / Bun | Match the global package's executable or shim; install and verify the registry's exact `latest` version. Multi-package pnpm 11 groups are refused to avoid removing other CLIs |
| Homebrew cask / formula | Resolve symlinks into Caskroom / Cellar and use that Homebrew installation |
| Native Claude, Copilot, Cursor Agent, OpenCode, Pi | Run the CLI's built-in update command and check its version afterward |
| Recent standalone Codex | Confirm `update` is an actual subcommand, then use Codex's installer-aware updater |
| Unknown older Codex, unsupported managers or mismatched global roots | Fail with a blocker rather than guessing or installing a second copy |

Package updates target `latest` (normally stable), not a preserved prerelease channel. Pi's installed package name is preserved, including the old `@mariozechner` name; this is not a package migration. Pi extensions are not updated.

Only the **first executable on the current process's absolute PATH** is updated. Activate the intended Node environment first. Shell aliases/functions, inactive installations, desktop apps, editor extensions, Nix, Scoop, WinGet, unresolved version-manager shims, and custom installer layouts are not automatically managed. Bun supports its default global layout and `BUN_INSTALL_GLOBAL_DIR`; custom `bunfig.toml` global directories may require manual updates.

## Reliability

- Updates run sequentially, avoiding conflicts in shared package managers.
- Absent agents are skipped; permissions are never elevated automatically.
- Commands run outside the project directory, with stdin closed and a ten-minute update timeout (`--timeout` to change it).
- Failed updates do not prevent attempts for the remaining agents; any failure produces exit code `1`.
- Every successful update is followed by an active-CLI version check. An unchanged version is reported as **checked**, not an unsupported “already latest” claim.
- Per-update logs are retained at the printed temporary path. Dry runs do not create update logs.

A successful command cannot guarantee a native updater has the newest upstream release. Network failures, package pins, and unknown installers are reported rather than hidden.

## Development

```bash
python3 -m unittest discover -s tests -v
```

Tests use isolated fake executables and package managers, never real agent updates. GitHub Actions runs them on Linux, macOS, and Windows.

The skill lives in `skills/update-clankers/SKILL.md`; its portable runner and Bash compatibility entry point are in `skills/update-clankers/scripts/`.

## License

MIT
