# Troubleshooting

Read only when the runner cannot complete. Inspect the printed failure and the affected agent's log, not every log.

| Blocker | Action |
| --- | --- |
| Python missing/older than 3.10 | Check `python3`, `python`, or Windows `py -3 --version`. If unavailable, report the prerequisite; don't install it silently. |
| Agent skipped unexpectedly | Inspect PATH and activate its intended Node/shell environment. Aliases/functions and inactive installations aren't visible. WSL updates Linux CLIs, not Windows CLIs. |
| npm prefix mismatch / unknown package shim | Compare the printed executable target with the manager's global package location. Don't install a second copy using an unrelated npm. |
| Unknown older Codex | Older releases have no `update` subcommand. Identify the original installer and its documented update procedure; never pass `update` as an agent prompt. |
| pnpm installation group | pnpm 11 can replace a whole group when adding one package. Update the group manually, preserving its other packages; the runner intentionally refuses this case. |
| Unsupported manager/layout | Nix, Scoop, WinGet, unresolved version-manager shims, and custom layouts need their owning installer/environment. Don't replace them with npm or downloaded binaries. |
| Permission denied, offline, package pinned | Report the exact blocker. Don't use sudo, bypass restrictions, or change pins automatically. |
| Version verification failed | The update didn't make the active CLI report the expected version. Inspect its path and log; don't report success. |
| Timeout | The command tree is stopped. Inspect the log before retrying; `--timeout 900` allows a longer update. |

## Installer behavior

- npm/pnpm/Bun: match global package metadata and its declared executable/shim, query the registry's `latest`, install that exact version, and verify the active CLI. This targets latest/stable, not an existing prerelease channel. Bun supports its default global layout and `BUN_INSTALL_GLOBAL_DIR`; custom `bunfig.toml` global directories may need manual handling.
- Homebrew: resolve into Caskroom/Cellar and use that prefix's `brew upgrade --cask/--formula`.
- Native installs: Claude/Copilot/Cursor use `update`; OpenCode uses `upgrade`; Pi uses `update --self`. Recent Codex uses its installer-aware `update` only after confirming the subcommand exists.
- Pi's installed npm package name is preserved; extensions, desktop apps, and editor plugins are out of scope.

Commands run sequentially with closed stdin and a temporary working directory, avoiding shared-manager conflicts and project-local config. Only the first executable on absolute PATH entries is targeted. Logs are retained at the printed temporary path. An unchanged native-updater version is **checked**, not proof of the newest upstream release.
