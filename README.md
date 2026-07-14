# update-clankers

A tiny cross-harness skill/Claude Code plugin that updates all your installed AI coding CLIs in one shot.

Detects which of these are on `PATH` and runs each update command in parallel:

| Agent          | Update command                        |
| -------------- | ------------------------------------- |
| `claude`       | `claude update`                       |
| `copilot`      | `copilot update`                      |
| `cursor-agent` | `cursor-agent update`                 |
| `opencode`     | `opencode upgrade`                    |
| `codex`        | `npm install -g @openai/codex@latest` |
| `pi`           | `pi update --self`                    |

Agents that aren't installed are skipped silently.

## Install

### Install for pi, Codex, Cursor, and Claude


```bash
npx skills add salmanrrana/update-clankers
```

Then invoke by asking your LLM to "update my clankers" or similar.

## Layout

```
.
├── .claude-plugin/plugin.json    # plugin manifest
└── skills/update-clankers/
    ├── SKILL.md                  # the skill itself
    └── scripts/update-clankers.sh # standalone updater script
```

## License

MIT
