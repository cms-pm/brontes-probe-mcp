# brontes-probe-mcp

A Model Context Protocol (MCP) server that gives AI assistants direct access
to a debug probe — flash firmware, halt/resume, read memory, and stream ITM
trace, all without leaving the conversation.

**Status: 0.2.1 — fully operational.**
Session lifecycle, probe operations, ITM/SWO trace, and lane supervision over
three concurrent transports (stdio MCP, Unix socket, loopback TCP).

## Quick start

Two deployment paths — pick the one that fits your platform:

| | |
|---|---|
| **Docker** | No Python install required; probe-agent CLI handles macOS USB limitations |
| **pip install** | No Docker required; works on all platforms |

### Docker on Linux

```bash
docker run -d --name brontes-probe-mcp \
  --device=/dev/bus/usb \
  -v "$HOME/.brontes-probe-mcp:/run/brontes-probe-mcp" \
  -v "$HOME/.brontes-probe-mcp/packs:/packs" \
  -e PROBE_BROKER_TRANSPORTS=stdio,socket \
  -e CMSIS_PACK_ROOT=/packs \
  ghcr.io/cms-pm/brontes-probe-mcp:0.2.1
```

Add to `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "brontes-probe-mcp": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--device=/dev/bus/usb",
        "-v", "${HOME}/.brontes-probe-mcp:/run/brontes-probe-mcp",
        "-v", "${HOME}/.brontes-probe-mcp/packs:/packs",
        "-e", "PROBE_BROKER_TRANSPORTS=stdio,socket",
        "-e", "CMSIS_PACK_ROOT=/packs",
        "ghcr.io/cms-pm/brontes-probe-mcp@sha256:TBD"
      ]
    }
  }
}
```

### Docker on macOS (Docker Desktop)

Docker Desktop cannot pass USB devices into containers. Install the CLI on the
host to manage the probe, then point the container at it:

```bash
# Install once
pip install brontes-probe-mcp

# Start the probe agent — auto-detects probe and target if unambiguous
brontes-probe-mcp-cli probe-agent start
```

`.mcp.json`:

```json
{
  "mcpServers": {
    "brontes-probe-mcp": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "${HOME}/.brontes-probe-mcp:/run/brontes-probe-mcp",
        "-v", "${HOME}/.brontes-probe-mcp/packs:/packs",
        "-e", "PROBE_BROKER_TRANSPORTS=stdio,socket",
        "-e", "CMSIS_PACK_ROOT=/packs",
        "-e", "PROBE_BROKER_GDB_HOST=host.docker.internal",
        "ghcr.io/cms-pm/brontes-probe-mcp@sha256:TBD"
      ]
    }
  }
}
```

`session_start` auto-discovers the running probe agent — no further
configuration needed. `session_stop` removes the Brontes session but leaves
the agent running for reuse.

### pip install (no Docker, all platforms)

Requires `arm-none-eabi-gdb` on `PATH` (install via your OS package manager
or [ARM toolchain download](https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads)).

```bash
pip install brontes-probe-mcp

# Start the probe agent — auto-detects probe and target if unambiguous
brontes-probe-mcp-cli probe-agent start
```

`.mcp.json`:

```json
{
  "mcpServers": {
    "brontes-probe-mcp": {
      "command": "brontes-probe-mcp-cli",
      "args": ["serve"]
    }
  }
}
```

Target auto-detection works when exactly one probe is connected and pyocd
recognises the board. If it fails, specify `--target` manually:

```bash
brontes-probe-mcp-cli probe-agent start --target stm32g474
```

### Connect (all options)

After adding `.mcp.json`, restart Claude Code (or run `/mcp` to reload
servers), then paste this into the conversation:

```
Connect to my debug probe. Call probe_discover to list attached probes.
Then call target_suggest with my MCU family or part number to find the
pyocd target string — use any board or chip info returned by probe_discover
as the query. If target_suggest returns no matches, call pack_update, then
pack_search to find the right CMSIS pack name, then pack_install (this may
take a minute), then retry target_suggest. Once you have the target string
and probe UID, call session_start.
```

Claude handles the full discovery flow automatically. If you already know
your target string you can skip straight to:

```
Call session_start with target="<your-target>".
```

---

## What it does

- **Probe discovery** — `probe_discover`, `target_suggest`,
  `pack_search`, `pack_install`, `pack_update`
- **Session lifecycle** — `session_start`, `session_stop`, `session_status`
  (reports `image_digest`, `image_tag`, `protocol_version`).
- **Probe operations** — `probe_program` (elf / bin / hex), `probe_halt`,
  `probe_resume`, `probe_reset` (soft / hard), `probe_mem_read`,
  `probe_blackbox_export`.
- **ITM / SWO trace** — `itm_stream_start`, `itm_stream_stop`,
  `recent_lines`.
- **Lane supervision** — `lane_status`, `lane_release`, `lane_resume`.

Three transport adapters bind concurrently over one shared `BrokerCore`
instance, controlled by `PROBE_BROKER_TRANSPORTS`:

| Transport | Default | Use case |
|---|---|---|
| `stdio` | ✓ | MCP stdio — one AI client |
| `socket` | ✓ | Unix-domain socket — local tool access |
| `tcp` | — | Loopback TCP with bearer token — sandbox / Docker Desktop |

## CLI

The `brontes-probe-mcp-cli` console script manages the server and probe agent:

```bash
brontes-probe-mcp-cli --version
brontes-probe-mcp-cli --config-dump            # print resolved config as JSON

# Start all configured transports (MCP server entry point for pip install)
brontes-probe-mcp-cli serve

# Probe agent — manages the host-side pyocd gdbserver daemon
brontes-probe-mcp-cli probe-agent start [--target TARGET] [--port PORT] [--probe-uid UID]
brontes-probe-mcp-cli probe-agent status       # prints JSON; exits 1 if not healthy
brontes-probe-mcp-cli probe-agent stop [--force]
```

If `--target` is omitted, `probe-agent start` auto-detects from a connected
probe. If multiple probes are attached, specify `--target` and `--probe-uid`.

## Configuration

All configuration is via `PROBE_BROKER_*` environment variables:

| Variable | Default | Description |
|---|---|---|
| `PROBE_BROKER_TRANSPORTS` | `stdio,socket` | Comma-separated active transports |
| `PROBE_BROKER_SOCKET_PATH` | `~/.brontes-probe-mcp/probe.sock` | Unix socket path |
| `PROBE_BROKER_TCP_HOST` | `127.0.0.1` | TCP bind address |
| `PROBE_BROKER_TCP_PORT` | `7172` | TCP port |
| `PROBE_BROKER_LANES` | `swd,itm_swo` | Active probe lanes |
| `PROBE_BROKER_BACKEND` | `pyocd` | Debug backend (`pyocd` or `openocd`) |
| `PROBE_BROKER_GDB_HOST` | `127.0.0.1` | GDB server host — set to `host.docker.internal` to connect to a host-side probe agent |
| `PROBE_BROKER_DEFAULT_PACK` | _(none)_ | Default CMSIS pack path — used by `target_suggest` and `session_start` when no `pack=` argument is supplied |
| `PROBE_BROKER_AGENT_STATE_DIR` | `~/.brontes-probe-mcp` | Directory where `probe-agent start` writes its state file and where `session_start` looks for a running agent. If `probe-agent start --state-dir` is set to a non-default path, set this variable to match |
| `PROBE_BROKER_DIGEST_CHECK` | `enforce` | Image digest verification (`enforce`, `warn`, `skip`) |

## Flash memory snapshot (`probe_blackbox_export`)

Capture a binary snapshot of the target's flash for archiving or diff:

```json
{
  "tool": "probe_blackbox_export",
  "arguments": {
    "out": "/tmp/snapshot.bin"
  }
}
```

Defaults to `0x08000000`–`0x08080000` (512 KB). Requires an active session.
Response includes `bytes_written` and `snapshot_at` (UTC ISO-8601).

See [docs/tutorials/blackbox-export.md](docs/tutorials/blackbox-export.md) for
custom address ranges, error cases, and snapshot comparison examples.

## Advanced deployment

### Docker Compose (socket, auto-restart)

```bash
curl -fsSL https://raw.githubusercontent.com/cms-pm/brontes-probe-mcp/main/docker-compose.yml \
  -o docker-compose.yml
docker compose up -d
```

### TCP loopback (sandbox / Docker Desktop without probe-agent)

```bash
docker run -d --name brontes-probe-mcp \
  -e PROBE_BROKER_TRANSPORTS=stdio,tcp \
  -e PROBE_BROKER_TOKEN=your-token-here \
  -p 127.0.0.1:7172:7172 \
  --device=/dev/bus/usb \
  ghcr.io/cms-pm/brontes-probe-mcp:0.2.1
```

### Pinning by digest

Pin by digest for production — the digest is the binary-level reproducibility
contract:

```bash
ghcr.io/cms-pm/brontes-probe-mcp@sha256:<digest>
```

Digests are published in [CHANGELOG.md](CHANGELOG.md) for each release.

## Client configuration

Configure your AI client to launch the server via the MCP stdio transport.

<!-- BEGIN client-configs -->
### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`
(Linux: `~/.config/Claude/claude_desktop_config.json`):

```json
{
  "brontes-probe-mcp": {
    "command": "docker",
    "args": [
      "run", "--rm", "-i",
      "--device=/dev/bus/usb",
      "-v", "${HOME}/.brontes-probe-mcp:/run/brontes-probe-mcp",
      "-v", "${HOME}/.brontes-probe-mcp/packs:/packs",
      "-e", "PROBE_BROKER_TRANSPORTS=stdio,socket",
      "-e", "CMSIS_PACK_ROOT=/packs",
      "ghcr.io/cms-pm/brontes-probe-mcp@sha256:TBD"
    ]
  }
}
```

macOS users: omit `--device=/dev/bus/usb` and add
`"-e", "PROBE_BROKER_GDB_HOST=host.docker.internal"` after running
`brontes-probe-mcp-cli probe-agent start` on the host.

### Claude Code

Add to `.mcp.json` in your project root (or `~/.claude.json` for global
config):

```json
{
  "mcpServers": {
    "brontes-probe-mcp": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--device=/dev/bus/usb",
        "-v", "${HOME}/.brontes-probe-mcp:/run/brontes-probe-mcp",
        "-v", "${HOME}/.brontes-probe-mcp/packs:/packs",
        "-e", "PROBE_BROKER_TRANSPORTS=stdio,socket",
        "-e", "CMSIS_PACK_ROOT=/packs",
        "ghcr.io/cms-pm/brontes-probe-mcp@sha256:TBD"
      ]
    }
  }
}
```

### Codex

Add to `~/.codex/config.json`:

```json
{
  "mcpServers": {
    "brontes-probe-mcp": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--device=/dev/bus/usb",
        "-v", "${HOME}/.brontes-probe-mcp:/run/brontes-probe-mcp",
        "-v", "${HOME}/.brontes-probe-mcp/packs:/packs",
        "-e", "PROBE_BROKER_TRANSPORTS=stdio,socket",
        "-e", "CMSIS_PACK_ROOT=/packs",
        "ghcr.io/cms-pm/brontes-probe-mcp@sha256:TBD"
      ]
    }
  }
}
```

### OpenCode

Add to `opencode.json` in your project root:

```json
{
  "mcp": {
    "servers": {
      "brontes-probe-mcp": {
        "type": "stdio",
        "command": "docker",
        "args": [
          "run", "--rm", "-i",
          "--device=/dev/bus/usb",
          "-v", "${HOME}/.brontes-probe-mcp:/run/brontes-probe-mcp",
          "-v", "${HOME}/.brontes-probe-mcp/packs:/packs",
          "-e", "PROBE_BROKER_TRANSPORTS=stdio,socket",
          "-e", "CMSIS_PACK_ROOT=/packs",
          "ghcr.io/cms-pm/brontes-probe-mcp@sha256:TBD"
        ]
      }
    }
  }
}
```
<!-- END client-configs -->

Replace `sha256:TBD` with the pinned digest from [CHANGELOG.md](CHANGELOG.md).

## Why "Brontes"

Brontes ("Thunderer") is one of the cyclops smiths in Hephaestus's forge —
the worker who hammers metal at the master's direction. The metaphor maps onto
the broker's role: client code directs the operation, the broker performs the
probe work.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
