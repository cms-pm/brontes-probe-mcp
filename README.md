# brontes-probe-mcp

> **Status: 0.0.0 placeholder.** This is a namespace reservation. The
> real implementation is not yet published. Do not depend on this repo
> or the `:0.0.0` image — both are placeholders held pending the first
> functional release.

## What this will be

A Model Context Protocol (MCP) server that exposes a multi-client
debug-probe broker for embedded-systems development. The server
mediates between one physical debug probe (SWD / JTAG, pyOCD-backed)
and multiple concurrent client processes — AI assistants, CLI tooling,
test runners — without requiring teardown of the underlying probe
session between operations.

Functional surface (subject to refinement before 1.0):

- Session lifecycle: start, stop, status (with image digest /
  protocol version reported).
- Probe operations: program (`elf` / `bin` / `hex`), halt, resume,
  reset (soft / hard), memory read, blackbox export.
- ITM / SWO trace lane: start / stop, recent-lines streaming.
- Lane supervision: status, release, resume.

Three concurrent transport adapters dispatch into one in-process
broker instance:

- **MCP stdio** — one MCP client per server process.
- **Unix-domain socket** — multi-client substrate for shared probe
  sessions.
- **Loopback TCP with bearer token** — sandbox / containerised AI
  client fallback.

The image-digest pin (sigstore-signed manifest) is the binary-level
anti-drift contract across the three transports.

## Why "Brontes"

Brontes ("Thunderer") is one of the cyclops smiths in Hephaestus's
forge — the worker who hammers metal at the master's direction. The
metaphor maps onto the broker's role: client code directs the
operation, the broker performs the probe work.

## License

Apache-2.0. See `LICENSE`.
