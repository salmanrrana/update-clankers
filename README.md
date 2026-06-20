# update-clankers

A tiny cross-harness skill/Claude Code plugin that updates all your installed AI coding CLIs in one shot.

Detects which of these are on `PATH` and runs each update command in parallel:

| Agent          | Update command                        |
| -------------- | ------------------------------------- |
| `claude`       | `claude update`                       |
| `cursor-agent` | `cursor-agent update`                 |
| `opencode`     | `opencode upgrade`                    |
| `codex`        | `npm install -g @openai/codex@latest` |
| `pi`           | `pi update --self`                    |

Agents that aren't installed are skipped silently.

## Install

### Install for pi, Codex, Cursor, and Claude

```bash
repo=/path/to/update-clankers
mkdir -p ~/.pi/agent/skills ~/.codex/skills ~/.cursor/skills-cursor ~/.claude/skills ~/.agents/skills
cp -R "$repo/skills/update-clankers" ~/.pi/agent/skills/
cp -R "$repo/skills/update-clankers" ~/.codex/skills/
cp -R "$repo/skills/update-clankers" ~/.cursor/skills-cursor/
cp -R "$repo/skills/update-clankers" ~/.claude/skills/
cp -R "$repo/skills/update-clankers" ~/.agents/skills/
```

Then ask any supported harness: "update my clankers".

You can also run the updater directly:

```bash
~/.agents/skills/update-clankers/scripts/update-clankers.sh
```

### As a Claude Code plugin

```bash
npx skills add salmanrrana/update-clankers
```

Then invoke by asking your LLM to "update my clankers" or similar.

### As a standalone skill (no plugin system)

Clone the skill straight into your user-level skills directory:

```bash
git clone https://github.com/salmanrrana/update-clankers.git /tmp/update-clankers
cp -r /tmp/update-clankers/skills/update-clankers ~/.claude/skills/
```

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
