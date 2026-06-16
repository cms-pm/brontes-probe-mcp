# brontes-probe-mcp

<img src="brontes.png" alt="brontes-probe-mcp logo" width="100%">

<p align="center">
  <a href="https://github.com/cms-pm/brontes-probe-mcp/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/cms-pm/brontes-probe-mcp/ci.yml?branch=main&style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/brontes-probe-mcp/"><img src="https://img.shields.io/pypi/v/brontes-probe-mcp?style=flat-square&label=PyPI" alt="PyPI"></a>
  <a href="https://pypi.org/project/brontes-probe-mcp/"><img src="https://img.shields.io/pypi/pyversions/brontes-probe-mcp?style=flat-square" alt="Python"></a>
  <a href="https://github.com/cms-pm/brontes-probe-mcp/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue?style=flat-square" alt="License"></a>
</p>
<p align="center">
  <img src="https://img.shields.io/badge/ARM-Cortex--M-0091BD?style=flat-square&logo=arm&logoColor=white" alt="ARM Cortex-M">
  <img src="https://img.shields.io/badge/STM32-compatible-03234B?style=flat-square&logo=stmicroelectronics&logoColor=white" alt="STM32">
  <img src="https://img.shields.io/badge/CMSIS--Pack-supported-blue?style=flat-square" alt="CMSIS-Pack">
  <img src="https://img.shields.io/badge/pyocd-backend-4CAF50?style=flat-square" alt="pyocd">
</p>
<p align="center">
  <img src="https://img.shields.io/badge/macOS-supported-000000?style=flat-square&logo=apple&logoColor=white" alt="macOS">
  <img src="https://img.shields.io/badge/Linux-supported-FCC624?style=flat-square&logo=linux&logoColor=black" alt="Linux">
  <img src="https://img.shields.io/badge/Windows-pip%20install-0078D4?style=flat-square&logo=windows&logoColor=white" alt="Windows">
  <img src="https://img.shields.io/badge/Docker-GHCR-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/MCP-stdio%20%7C%20socket%20%7C%20TCP-7C3AED?style=flat-square" alt="MCP">
</p>

A Model Context Protocol (MCP) server that gives AI assistants direct access
to a debug probe — flash firmware, halt/resume, read memory, and stream ITM
trace, all without leaving the conversation.

**Status: 0.3.0 — first-use hardened.**
Session lifecycle, probe operations, ITM/SWO trace (raw + decoded export),
CMSIS pack-cache recovery, and lane supervision over three concurrent
transports (stdio MCP, Unix socket, loopback TCP). All seven first-adopter
friction points from the 0.2.2 retrospective are addressed — see
[CHANGELOG.md](https://github.com/cms-pm/brontes-probe-mcp/blob/main/CHANGELOG.md#030---2026-06-16).

## Quick start

Three steps: configure, start the probe agent (macOS / pip only), connect.

---

### Step 1 — Configure

Pick your deployment. Each section below includes a prompt you can paste
directly into Claude Code to write `.mcp.json` automatically, or add it
manually if you prefer.

#### Docker on Linux (recommended)

**Paste into Claude Code:**

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
        "ghcr.io/cms-pm/brontes-probe-mcp@sha256:4b919af0673dea01444d445b5a1abcef4ea904562afbb73a3b11cdd038bcf005"
      ]
    }
  }
}

Then pull the image:
docker pull ghcr.io/cms-pm/brontes-probe-mcp@sha256:4b919af0673dea01444d445b5a1abcef4ea904562afbb73a3b11cdd038bcf005

Then tell me to restart Claude Code to load the new server.
```

Replace `sha256:4b919af0673dea01444d445b5a1abcef4ea904562afbb73a3b11cdd038bcf005` with the digest from [CHANGELOG.md](https://github.com/cms-pm/brontes-probe-mcp/blob/main/CHANGELOG.md).

#### Docker on macOS (Docker Desktop)

Docker Desktop cannot pass USB devices into containers. First install the
host CLI:

```bash
pip install brontes-probe-mcp
```

**Paste into Claude Code:**

```
Add brontes-probe-mcp to .mcp.json in this project, creating it if needed:

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
        "ghcr.io/cms-pm/brontes-probe-mcp@sha256:4b919af0673dea01444d445b5a1abcef4ea904562afbb73a3b11cdd038bcf005"
      ]
    }
  }
}

Then tell me to restart Claude Code to load the new server.
```

#### pip install (no Docker, all platforms)

**Pre-flight checks** — these three commands should succeed *before* you start
the agent. They cover the friction points from real first-use:

```bash
# 1. pip is available (bootstrap with ensurepip if your venv was created without it)
python -m pip --version  ||  python -m ensurepip --upgrade

# 2. arm-none-eabi-gdb is on PATH (install via your OS package manager or
#    https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads)
arm-none-eabi-gdb --version

# 3. Install brontes-probe-mcp and confirm the console script is on PATH
pip install brontes-probe-mcp
brontes-probe-mcp-cli --version
```

If `brontes-probe-mcp-cli` is not found, your shell's `PATH` doesn't include
the directory `pip` wrote the script to. Either re-source your venv activate
script (`source .venv/bin/activate`) or use `python -m brontes_probe_mcp` /
`python -m brontes_probe_mcp.cli` directly.

**Paste into Claude Code:**

```
Add brontes-probe-mcp to .mcp.json in this project, creating it if needed:

{
  "mcpServers": {
    "brontes-probe-mcp": {
      "command": "brontes-probe-mcp-cli",
      "args": ["serve"]
    }
  }
}

Then tell me to restart Claude Code to load the new server.
```

---

### Step 2 — Start the probe agent (macOS and pip only)

> **Docker on Linux users skip this step** — the container manages pyocd
> internally.

Run this once before each session (keep it running in the background):

```bash
# Auto-detects probe and target if exactly one probe is connected
brontes-probe-mcp-cli probe-agent start
```

If auto-detection fails (multiple probes, or board not recognised by pyocd):

```bash
brontes-probe-mcp-cli probe-agent start --target stm32g474 --probe-uid <uid>
```

`session_start` auto-discovers the running agent — no extra configuration
needed. `session_stop` removes the Brontes session but leaves the agent
running for reuse.

---

### Step 3 — Connect

After restarting Claude Code (or running `/mcp` to reload), paste this into
the conversation:

```
Call probe_discover to list connected debug probes. Use any board or chip
information from the results to call target_suggest and find the pyocd
target string — pyocd usually wants the full subfamily/package suffix
(for example "stm32g474ceux", not bare "stm32g474"). If target_suggest
returns no matches, call pack_update to refresh the pack index, then
pack_search to find the right CMSIS pack name, then pack_install (may
take a minute), then retry target_suggest. If pack_search or pack_install
fails with pack_index_corrupt, call pack_cache_reset to wipe and rebuild
the pyOCD pack index, then retry. Once you have the target string, call
session_start — omit probe_uid if only one probe is connected, otherwise
pass the uid from probe_discover. If you have a CMSIS pack on disk, you
can pass pack=/path/to/pack to bypass the global pack index entirely.
```

If you already know your target string and pack path (fastest path):

```
Call session_start with target="stm32g474ceux" and pack="/path/to/STM32G4xx_DFP".
```

---

## What it does

- **Probe discovery** — `probe_discover`, `target_suggest` (with
  local-PDSC bypass), `pack_search`, `pack_install`, `pack_update`,
  `pack_cache_reset` (recover from corrupt pyOCD pack index).
- **Session lifecycle** — `session_start`, `session_stop`, `session_status`
  (reports `image_digest`, `image_tag`, `protocol_version`, `session_id`).
- **Probe operations** — `probe_program` (elf / bin / hex), `probe_halt`,
  `probe_resume`, `probe_reset` (`soft`, `hard`, `sw`, `system`, `core`,
  `backend_default` — each maps to a documented `monitor reset` command
  and the exact command is echoed back), `probe_mem_read`,
  `probe_blackbox_export` (explicit range required — see below).
- **ITM / SWO trace** — `itm_stream_start`, `itm_stream_stop`,
  `itm_stream_export` (raw bytes + decoded JSONL artifact),
  `recent_lines` (with `session_id` / `method` / `lane` filters).
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

# Generic one-shot JSON-RPC client over the running Unix socket
brontes-probe-mcp-cli call session_status
brontes-probe-mcp-cli call mem_read --json '{"addr":536870912,"length":4}'
brontes-probe-mcp-cli call session_start --json '{"target":"stm32g474ceux"}'
```

`call` opens a short-lived connection to the running broker's socket, sends
one envelope, prints the reply, and exits. Exit codes: `0` on a non-error
response, `1` on a transport failure or `{"error": ...}` envelope, `2` on
invalid `--json` input.

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

Capture a binary snapshot of the target's memory for archiving or diff.
**As of 0.3.0 an explicit range is required** — the previous 512 KB flash
default took roughly four minutes for a 48-byte evidence slice, so we
removed it. Pass exactly one of:

```jsonc
// (1) explicit start/end
{"tool": "probe_blackbox_export",
 "arguments": {"out": "/tmp/snapshot.bin",
               "start_addr": 134217728, "end_addr": 134742016}}

// (2) start + length
{"tool": "probe_blackbox_export",
 "arguments": {"out": "/tmp/snapshot.bin",
               "addr": 536870912, "length": 48}}

// (3) named region from the advisory registry (sram_blackbox = 0x20000000, 64 B)
{"tool": "probe_blackbox_export",
 "arguments": {"out": "/tmp/snapshot.bin", "region": "sram_blackbox"}}
```

Calling with none of those raises `ValueError`. Response includes
`bytes_written`, `snapshot_at` (UTC ISO-8601), and `resolved_addr` /
`resolved_length` / `resolved_from_region` recording exactly which range
the call resolved to.

See [docs/tutorials/blackbox-export.md](https://github.com/cms-pm/brontes-probe-mcp/blob/main/docs/tutorials/blackbox-export.md) for
custom address ranges, error cases, and snapshot comparison examples.

## Troubleshooting first-use

These are the friction points the 0.2.2 first adopter actually hit, with
the fix path each one now has in 0.3.0:

| Symptom | Likely cause | Fix |
|---|---|---|
| `brontes-probe-mcp-cli: command not found` after `pip install` | Console script not on `PATH` | Re-activate your venv (`source .venv/bin/activate`) or run `python -m brontes_probe_mcp.cli` |
| `python -m pip` not found inside a fresh venv | Venv created without `pip` | `python -m ensurepip --upgrade` |
| `session_start(target="stm32g474")` → target unknown | pyOCD wants the full subfamily/package string | Use `target_suggest` to get the exact string (e.g. `"stm32g474ceux"`) — or pass `pack=/path/to/STM32G4xx_DFP` if you have a local CMSIS pack |
| `pack_search` / `pack_install` / `target_suggest` raise `pack_index_corrupt` (`JSONDecodeError`) | pyOCD's global pack index is malformed | Call `pack_cache_reset` (wipes `~/.pyocd/packs/index/` and re-runs `pyocd pack update`), then retry |
| Watchdog test reports `boot_outcome=SRON` instead of the expected `WDGR` | Debug-domain reset masked the IWDG path | Read the docstring on `reset(kind=...)` — `hard`/`sw`/`system` reset the debug domain; `soft` is the right choice for IWDG firmware watchdog tests. The `reset_command_echo` and `reset_cause_hint` fields in the response confirm what actually happened |
| `blackbox_export` raises `ValueError: range required` | Pre-0.3.0 default range was removed | Pass `(addr, length)`, `(start_addr, end_addr)`, or `region="sram_blackbox"` |
| Audit log noisy across multiple sessions | `recent_lines` returned server-wide history | Pass `session_id=` (from `session_status`); also accepts `method=` and `lane=` filters |
| `BrokenPipeError` traceback on `Ctrl-C` shutdown | Pre-0.3.0 transport handler raised on the half-closed socket | Already fixed — quiet `DEBUG`-level log line; no action needed |

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
  ghcr.io/cms-pm/brontes-probe-mcp:0.3.0
```

### Pinning by digest

Pin by digest for production — the digest is the binary-level reproducibility
contract:

```bash
ghcr.io/cms-pm/brontes-probe-mcp@sha256:<digest>
```

Digests are published in [CHANGELOG.md](https://github.com/cms-pm/brontes-probe-mcp/blob/main/CHANGELOG.md) for each release.

## Client configuration

Configure your AI client to launch the server via the MCP stdio transport.

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
      "-v", "${HOME}/.brontes-probe-mcp/packs:/packs",
      "-e", "PROBE_BROKER_TRANSPORTS=stdio,socket",
      "-e", "CMSIS_PACK_ROOT=/packs",
      "ghcr.io/cms-pm/brontes-probe-mcp@sha256:4b919af0673dea01444d445b5a1abcef4ea904562afbb73a3b11cdd038bcf005"
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
        "-v", "${HOME}/.brontes-probe-mcp/packs:/packs",
        "-e", "PROBE_BROKER_TRANSPORTS=stdio,socket",
        "-e", "CMSIS_PACK_ROOT=/packs",
        "ghcr.io/cms-pm/brontes-probe-mcp@sha256:4b919af0673dea01444d445b5a1abcef4ea904562afbb73a3b11cdd038bcf005"
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
        "ghcr.io/cms-pm/brontes-probe-mcp@sha256:4b919af0673dea01444d445b5a1abcef4ea904562afbb73a3b11cdd038bcf005"
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
          "ghcr.io/cms-pm/brontes-probe-mcp@sha256:4b919af0673dea01444d445b5a1abcef4ea904562afbb73a3b11cdd038bcf005"
        ]
      }
    }
  }
}
```
<!-- END client-configs -->

Replace `sha256:4b919af0673dea01444d445b5a1abcef4ea904562afbb73a3b11cdd038bcf005` with the pinned digest from [CHANGELOG.md](https://github.com/cms-pm/brontes-probe-mcp/blob/main/CHANGELOG.md).

## Why "Brontes"

Brontes ("Thunderer") is one of the cyclops smiths in Hephaestus's forge —
the worker who hammers metal at the master's direction. The metaphor maps onto
the broker's role: client code directs the operation, the broker performs the
probe work.

## Changelog

See [CHANGELOG.md](https://github.com/cms-pm/brontes-probe-mcp/blob/main/CHANGELOG.md).

## License

Apache-2.0. See [LICENSE](https://github.com/cms-pm/brontes-probe-mcp/blob/main/LICENSE).
