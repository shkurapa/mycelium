# OpenClaw Setup Guide

Guide for installing OpenClaw, creating agents with separate workspaces, and preparing the diagnostics-otel plugin. Written for a fresh Ubuntu server, but the steps apply to any Linux environment.

Once OpenClaw is running, see the main [README](../README.md) for Mycelium integration and the metrics dashboard.

## Prerequisites

- Node.js 20+ (via nvm recommended)
- An Anthropic API key (or another supported LLM provider)

---

## 1. Install OpenClaw

```bash
npm install -g openclaw
```

Verify:

```bash
openclaw --version
```

### First-time setup

The onboarding wizard walks through provider selection, API key, and gateway service installation:

```bash
openclaw onboard --install-daemon
```

This creates `~/.openclaw/` with the default workspace and `openclaw.json` configuration, and installs the gateway as a systemd user service.

If you prefer to configure manually:

```bash
openclaw configure
```

### Start the gateway

```bash
openclaw gateway start
```

Verify it's running:

```bash
openclaw status
```

---

## 2. Install the diagnostics-otel plugin

The OTEL plugin exports telemetry (traces, metrics, logs) from OpenClaw. It ships with OpenClaw but its npm dependencies may not be installed.

```bash
openclaw plugins install diagnostics-otel
```

If you see `Cannot find module '@opentelemetry/api'` when running `openclaw status`, install the dependencies manually:

```bash
cd $(dirname $(which openclaw))/../lib/node_modules/openclaw/extensions/diagnostics-otel
npm install
```

Then restart the gateway:

```bash
openclaw gateway restart
```

The plugin is now installed but not yet configured with an endpoint. Mycelium's adapter command handles that — see the [Metrics Dashboard](../README.md#metrics-dashboard) section of the main README.

---

## 3. Create agents

### Default agent

OpenClaw creates a default `main` agent during onboarding. Its workspace is at `~/.openclaw/workspace/`.

### Adding named agents with separate workspaces

Each agent can have its own workspace with a distinct personality, memory, and tools:

```bash
openclaw agents add researcher --workspace ~/.openclaw/workspace-researcher
openclaw agents add coder --workspace ~/.openclaw/workspace-coder
```

List agents:

```bash
openclaw agents list
```

Set agent identity:

```bash
openclaw agents set-identity --agent researcher --name "Researcher" --emoji "🔬"
```

### Agent workspace files

Each workspace directory contains Markdown files that define the agent's behavior:

```
~/.openclaw/workspace-researcher/
├── SOUL.md          # Personality, values, communication style, hard limits
├── IDENTITY.md      # Name, emoji, avatar, theme
├── AGENTS.md        # Sub-agent definitions and delegation rules
├── USER.md          # Info about the user the agent works with
├── TOOLS.md         # Tool usage instructions and constraints
├── HEARTBEAT.md     # Scheduled/periodic task instructions
├── MEMORY.md        # Persistent memory across sessions
└── memory/          # Additional memory files
```

`SOUL.md` is the most important — it loads at the start of every session and shapes all agent behavior. Edit it to define the agent's role, tone, constraints, and priorities.

### Run an agent

```bash
openclaw agent --message "Summarize the latest research on multi-agent coordination"
openclaw agent --agent researcher --message "Find papers on emergent behavior in LLM agents"
openclaw agent --agent coder --message "Write a Python script to parse JSONL files" --thinking medium
```

---

## 4. Configuration reference

### `~/.openclaw/openclaw.json`

Central configuration file. Key sections:

| Section | Purpose |
|---------|---------|
| `provider` | LLM provider and API key |
| `agents` | Named agents and their workspace paths |
| `plugins` | Plugin configuration (e.g. `diagnostics-otel`) |
| `gateway` | Gateway settings (port, host) |

Changes to this file require a gateway restart:

```bash
openclaw gateway restart
```

### Gateway management

| Command | Description |
|---------|-------------|
| `openclaw gateway start` | Start the gateway service |
| `openclaw gateway stop` | Stop the gateway service |
| `openclaw gateway restart` | Restart (picks up config changes) |
| `openclaw status` | Show gateway, plugins, and agent status |

---

## Troubleshooting

### `diagnostics-otel failed to load: Cannot find module '@opentelemetry/api'`

The plugin's npm dependencies aren't installed. See [Step 2](#2-install-the-diagnostics-otel-plugin).

### Gateway won't start

Check logs with `openclaw gateway logs` or run `openclaw status` for diagnostic output. Common causes:
- Missing or invalid API key in `openclaw.json`
- Port conflict (another process on the gateway port)

### Gateway config changes not taking effect

OpenClaw reads `~/.openclaw/openclaw.json` at startup. After any changes, restart the gateway:

```bash
openclaw gateway restart
```

### Checking overall status

```bash
openclaw status    # gateway health, loaded plugins, registered agents
```

---

## Next steps

With OpenClaw running and agents configured, proceed to the main [README](../README.md) to:

1. Install the Mycelium CLI and connect it to OpenClaw (`mycelium adapter add openclaw`)
2. Enable OTEL metrics export (`--step=otel`)
3. Start the metrics dashboard (`mycelium metrics start --otel`)
