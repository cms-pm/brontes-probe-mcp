# brontes-probe-mcp

A Model Context Protocol (MCP) server that exposes a debug-probe broker for
embedded-systems development. The server maintains one persistent probe
session (SWD / JTAG, pyOCD-backed) accessible to multiple client tools —
AI assistants, CLI tooling, test runners — without requiring teardown and
re-establishment of the hardware connection between operations.

**Status: 0.1.0 — fully operational.**
Session lifecycle, probe operations, ITM/SWO trace, and lane supervision over
three concurrent transports (stdio MCP, Unix socket, loopback TCP).

## What it does

- **Session lifecycle** — `session_start`, `session_stop`, `session_status`
  (reports `image_digest`, `image_tag`, `protocol_version`).
- **Probe operations** — `program` (elf / bin / hex), `halt`, `resume`,
  `reset` (soft / hard), `mem_read`, `blackbox_export`.
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

## Quick start

The recommended deployment path is the container image. A PyPI wheel is not
yet published.

**Option A — Unix socket (Linux, recommended)**

```bash
docker run -d --name brontes-probe-mcp \
  -v "$HOME/.brontes-probe-mcp:/run/brontes-probe-mcp" \
  --device=/dev/bus/usb \
  ghcr.io/cms-pm/brontes-probe-mcp:0.1.0
```

**Option B — Probe agent split (macOS / Docker Desktop)**

Docker Desktop on macOS cannot pass USB devices into containers. Run pyocd
natively as a probe agent; the container connects to it over TCP:

```bash
# Terminal 1 — probe agent (runs on the macOS host, owns the USB device)
pyocd gdbserver --persist --target <your-target> --port 3333

# .mcp.json — container connects to the host agent, no --device needed
```

```json
{
  "brontes-probe-mcp": {
    "command": "docker",
    "args": [
      "run", "--rm", "-i",
      "-v", "${HOME}/.brontes-probe-mcp:/run/brontes-probe-mcp",
      "-v", "${HOME}/.brontes-probe-mcp/packs:/packs",
      "-e", "PROBE_BROKER_TRANSPORTS=stdio,socket",
      "-e", "CMSIS_PACK_ROOT=/packs",
      "-e", "PROBE_BROKER_GDB_HOST=host.docker.internal",
      "ghcr.io/cms-pm/brontes-probe-mcp@sha256:77e58b86015ddf0b36fba47d267669ed7493ea5ff6794dbe80628fa4dce13ae7"
    ]
  }
}
```

`session_start` will connect to the running probe agent rather than spawning
pyocd internally. `session_stop` removes the Brontes session record but does
not terminate the agent — it persists for reuse.

**Option C — TCP loopback (no probe agent required)**

```bash
docker run -d --name brontes-probe-mcp \
  -e PROBE_BROKER_TRANSPORTS=stdio,tcp \
  -e PROBE_BROKER_TOKEN=your-token-here \
  -p 127.0.0.1:7172:7172 \
  --device=/dev/bus/usb \
  ghcr.io/cms-pm/brontes-probe-mcp:0.1.0
```

**Option D — Docker Compose (socket, auto-restart)**

```bash
curl -fsSL https://raw.githubusercontent.com/cms-pm/brontes-probe-mcp/main/docker-compose.yml \
  -o docker-compose.yml
docker compose up -d
```

Pin by digest for production use — the digest is the binary-level
reproducibility contract:

```bash
ghcr.io/cms-pm/brontes-probe-mcp@sha256:<digest>
```

Digests are published in [CHANGELOG.md](CHANGELOG.md) for each release.

### First session (Claude Code)

Once the server is registered, paste **Phase 1** into Claude Code to write
`.mcp.json` and pull the image, then **Phase 2** after the restart to connect.

**Phase 1 — configure** (paste into Claude Code, press Enter):

```
Add brontes-probe-mcp to .mcp.json in this project, creating it if needed:

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
        "ghcr.io/cms-pm/brontes-probe-mcp@sha256:77e58b86015ddf0b36fba47d267669ed7493ea5ff6794dbe80628fa4dce13ae7"
      ]
    }
  }
}

Then run this shell command to pre-fetch the image:
docker pull ghcr.io/cms-pm/brontes-probe-mcp@sha256:77e58b86015ddf0b36fba47d267669ed7493ea5ff6794dbe80628fa4dce13ae7

Then tell me to restart Claude Code to load the new server.
```

**Restart** Claude Code (or run `/mcp` to reload servers).

**Phase 2 — discover and connect** (paste after restart):

```
Call probe_discover to list attached debug probes. Then call target_suggest
with my MCU family (e.g. "stm32g4") to find the target string. If
target_suggest returns no results, call pack_search with the MCU family to
find the right CMSIS pack name, then call pack_install to install it
(this may take a minute), then retry target_suggest. Once you have the
probe UID and target string, call session_start.
```

`probe_discover`, `target_suggest`, `pack_search`, and `pack_install` do
not require an active session. Installed packs are written to
`~/.brontes-probe-mcp/packs/` on the host and persist across container
restarts — `pack_install` only runs once per MCU family.

## Client configuration

Configure your AI client to launch the container via the MCP stdio transport.

<!-- BEGIN client-configs -->
### Claude Desktop

Add the following entry to the `mcpServers` object in `~/Library/Application Support/Claude/claude_desktop_config.json` (Linux: `~/.config/Claude/claude_desktop_config.json`):

```json
{
  "brontes-probe-mcp": {
    "command": "docker",
    "args": [
      "run", "--rm", "-i",
      "--device=/dev/bus/usb",
      "-v", "${HOME}/.brontes-probe-mcp:/run/brontes-probe-mcp",
      "-e", "PROBE_BROKER_TRANSPORTS=stdio,socket",
      "ghcr.io/cms-pm/brontes-probe-mcp@sha256:77e58b86015ddf0b36fba47d267669ed7493ea5ff6794dbe80628fa4dce13ae7"
    ]
  }
}
```

### Claude Code

Add to `.mcp.json` in your project root (or `~/.claude.json` for global config):

```json
{
  "mcpServers": {
    "brontes-probe-mcp": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--device=/dev/bus/usb",
        "-v", "${HOME}/.brontes-probe-mcp:/run/brontes-probe-mcp",
        "-e", "PROBE_BROKER_TRANSPORTS=stdio,socket",
        "ghcr.io/cms-pm/brontes-probe-mcp@sha256:77e58b86015ddf0b36fba47d267669ed7493ea5ff6794dbe80628fa4dce13ae7"
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
        "-e", "PROBE_BROKER_TRANSPORTS=stdio,socket",
        "ghcr.io/cms-pm/brontes-probe-mcp@sha256:77e58b86015ddf0b36fba47d267669ed7493ea5ff6794dbe80628fa4dce13ae7"
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
          "-e", "PROBE_BROKER_TRANSPORTS=stdio,socket",
          "ghcr.io/cms-pm/brontes-probe-mcp@sha256:77e58b86015ddf0b36fba47d267669ed7493ea5ff6794dbe80628fa4dce13ae7"
        ]
      }
    }
  }
}
```
<!-- END client-configs -->

Replace `sha256:TBD` with the pinned digest for your release. The digest is
the binary-level reproducibility contract — pin it, don't float on a tag.

## CLI

The `brontes-probe-mcp-cli` console script provides one-shot method
invocations for shell scripts and debugging:

```bash
brontes-probe-mcp-cli --version
brontes-probe-mcp-cli --config-dump   # print resolved config as JSON
```

Full verb surface (`session-start`, `program`, `halt`, `mem-read`, etc.)
lands with the transport implementation.

## Configuration

All configuration is via `PROBE_BROKER_*` environment variables:

| Variable | Default | Description |
|---|---|---|
| `PROBE_BROKER_TRANSPORTS` | `stdio,socket` | Comma-separated active transports |
| `PROBE_BROKER_SOCKET_PATH` | `/run/brontes-probe-mcp/probe.sock` | Unix socket path |
| `PROBE_BROKER_TCP_HOST` | `127.0.0.1` | TCP bind address |
| `PROBE_BROKER_TCP_PORT` | `7172` | TCP port |
| `PROBE_BROKER_LANES` | `swd,itm_swo` | Active probe lanes |
| `PROBE_BROKER_BACKEND` | `pyocd` | Debug backend (`pyocd` or `openocd`) |
| `PROBE_BROKER_GDB_HOST` | `127.0.0.1` | GDB server host — set to `host.docker.internal` to connect to an external probe agent instead of spawning pyocd locally |
| `PROBE_BROKER_DEFAULT_PACK` | _(none)_ | Default CMSIS pack path — used by `target_suggest` and `session_start` when no `pack=` argument is supplied |
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

## Why "Brontes"

Brontes ("Thunderer") is one of the cyclops smiths in Hephaestus's forge —
the worker who hammers metal at the master's direction. The metaphor maps onto
the broker's role: client code directs the operation, the broker performs the
probe work.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
