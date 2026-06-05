# brontes-probe-mcp

A Model Context Protocol (MCP) server that exposes a multi-client debug-probe
broker for embedded-systems development. The server mediates between one
physical debug probe (SWD / JTAG, pyOCD-backed) and multiple concurrent
client processes — AI assistants, CLI tooling, test runners — without
requiring teardown of the underlying probe session between operations.

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
| `socket` | ✓ | Unix-domain socket — multi-client substrate |
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

**Option B — TCP loopback (Docker Desktop / macOS)**

```bash
docker run -d --name brontes-probe-mcp \
  -e PROBE_BROKER_TRANSPORTS=stdio,tcp \
  -e PROBE_BROKER_TOKEN=your-token-here \
  -p 127.0.0.1:7172:7172 \
  --device=/dev/bus/usb \
  ghcr.io/cms-pm/brontes-probe-mcp:0.1.0
```

**Option C — Docker Compose (socket, auto-restart)**

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
