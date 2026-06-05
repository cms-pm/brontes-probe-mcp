# Tutorial: Flash Memory Snapshot with `probe_blackbox_export`

`probe_blackbox_export` captures a binary snapshot of the target's flash memory
by issuing a GDB `dump binary memory` command. The result is a raw binary file
you can archive, diff, or analyse offline.

## Prerequisites

- An active session (`session_start` must have been called and returned `"healthy"`)
- Sufficient filesystem space for the snapshot (`end_addr − start_addr` bytes)

## Basic usage

```json
{
  "tool": "probe_blackbox_export",
  "arguments": {
    "out": "/tmp/snapshot.bin"
  }
}
```

Default memory range: `0x08000000` – `0x08080000` (512 KB, covers standard
STM32 / nRF52 flash regions).

## Custom range

```json
{
  "tool": "probe_blackbox_export",
  "arguments": {
    "out": "/tmp/snapshot.bin",
    "start_addr": 134217728,
    "end_addr":   134348800
  }
}
```

`start_addr` and `end_addr` are decimal integers (bytes). The example above
is equivalent to `0x08000000`–`0x08020000` (128 KB).

## Response

```json
{
  "out": "/tmp/snapshot.bin",
  "bytes_written": 524288,
  "snapshot_at": "2026-06-04T12:34:56+00:00"
}
```

| Field | Type | Description |
|---|---|---|
| `out` | string | Absolute path to the snapshot file |
| `bytes_written` | integer | File size after the GDB dump completed |
| `snapshot_at` | string (ISO-8601) | UTC timestamp of the capture |

## Error cases

| Condition | Response |
|---|---|
| No active session | `{"error": {"kind": "session_required", ...}}` |
| GDB exits non-zero | `RuntimeError` propagated as `{"error": {"kind": "broker_internal_error", ...}}` |
| Output file absent after dump | `bytes_written: 0` (GDB wrote nothing; check target connectivity) |

## Comparing snapshots

```bash
cmp /tmp/snapshot-before.bin /tmp/snapshot-after.bin && echo "identical" || echo "differs"
xxd /tmp/snapshot-before.bin | head -4
```

## Notes

- The session must remain healthy for the duration of the dump. Long flash
  regions (>1 MB) may take several seconds over SWD.
- `out` must be writable by the broker process. Use an absolute path to avoid
  ambiguity.
- The snapshot is a flat binary dump starting at `start_addr`. It is not an
  ELF or Intel HEX file.
