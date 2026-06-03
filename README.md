# update-clankers

A tiny skill that updates all your installed AI coding CLIs in one shot.

Detects which of these are on `PATH` and runs each update command in parallel:

| Agent          | Update command                        |
| -------------- | ------------------------------------- |
| `claude`       | `claude update`                       |
| `cursor-agent` | `cursor-agent update`                 |
| `opencode`     | `opencode upgrade`                    |
| `codex`        | `npm install -g @openai/codex@latest` |
| `pi`           | `pi update pi`                        |

Agents that aren't installed are skipped silently.

## Install

```bash
npx skills add salmanrrana/update-clankers
```

(Replace `<github-user>` with this repo's owner.)

Then invoke by asking your llm to "update my clankers" or similar.

### As a standalone skill (no plugin system)

Clone the skill straight into your user-level skills directory:

```bash
git clone https://github.com/<github-user>/update-clankers.git /tmp/update-clankers
cp -r /tmp/update-clankers/skills/update-clankers ~/.claude/skills/
```

## Layout

```
.
├── .claude-plugin/plugin.json    # plugin manifest
└── skills/update-clankers/
    └── SKILL.md                  # the skill itself
```

## License

MIT
