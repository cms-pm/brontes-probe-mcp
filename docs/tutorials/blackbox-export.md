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

---

## Firmware side: structuring memory for export

`probe_blackbox_export` captures a flat binary range. If your firmware places
a known struct at a predictable address you can extract structured telemetry
from the dump offline — no JTAG connection needed after the fact.

Two patterns are shown below: a simple fixed-address struct (zero deps) and a
ring-buffer event log that survives soft resets.

### Pattern 1 — fixed-address telemetry struct (C)

Place a `volatile` struct at a specific RAM address. Stamp it with a magic
word so you can detect valid data in the dump.

```c
/* blackbox_telemetry.h */
#include <stdint.h>
#include <stdbool.h>

#define TELEMETRY_BASE_ADDR  0x20007F00UL   /* top of STM32G4 RAM — adjust to fit */
#define TELEMETRY_MAGIC      0xFADE5AFEUL
#define TELEMETRY_VERSION    0x00010000UL

typedef struct {
    uint32_t magic;            /* 0xFADE5AFE — integrity sentinel              */
    uint32_t version;          /* layout version; bump when fields change       */
    uint32_t program_counter;  /* current execution PC                          */
    uint32_t instruction_count;
    uint32_t last_opcode;
    uint32_t system_tick_ms;   /* HAL_GetTick() or equivalent                   */
    uint32_t test_value;       /* arbitrary known value; 0xDEADBEEF at init     */
    uint32_t checksum;         /* XOR of all fields above; recompute on write   */
} telemetry_t;

/* Compile-time size guard — do not remove */
_Static_assert(sizeof(telemetry_t) == 32, "telemetry_t must be 32 bytes");
```

```c
/* blackbox_telemetry.c */
#include "blackbox_telemetry.h"

static volatile telemetry_t * const g_tel =
    (volatile telemetry_t *)TELEMETRY_BASE_ADDR;

static uint32_t checksum(void) {
    return g_tel->magic ^ g_tel->version ^
           g_tel->program_counter ^ g_tel->instruction_count ^
           g_tel->last_opcode ^ g_tel->system_tick_ms ^ g_tel->test_value;
}

void telemetry_init(void) {
    g_tel->magic            = TELEMETRY_MAGIC;
    g_tel->version          = TELEMETRY_VERSION;
    g_tel->program_counter  = 0;
    g_tel->instruction_count = 0;
    g_tel->last_opcode      = 0;
    g_tel->system_tick_ms   = 0;
    g_tel->test_value       = 0xDEADBEEF;
    g_tel->checksum         = checksum();
}

void telemetry_update(uint32_t pc, uint32_t insn_count,
                      uint32_t opcode, uint32_t tick_ms) {
    g_tel->program_counter   = pc;
    g_tel->instruction_count = insn_count;
    g_tel->last_opcode       = opcode;
    g_tel->system_tick_ms    = tick_ms;
    g_tel->checksum          = checksum();
}

bool telemetry_valid(void) {
    return g_tel->magic   == TELEMETRY_MAGIC   &&
           g_tel->version == TELEMETRY_VERSION &&
           g_tel->checksum == checksum();
}
```

After export, extract fields from the binary. The struct starts at
`TELEMETRY_BASE_ADDR − start_addr` bytes into the file.

> **Endianness**: the decoder below assumes a little-endian target (all
> Cortex-M parts). If your MCU runs big-endian, swap `"<8I"` for `">8I"`.

> **ISR safety**: `telemetry_valid()` reads all fields and then recomputes
> the checksum in two separate passes through `g_tel`. If your firmware
> updates telemetry from an ISR context, disable interrupts around the call
> to prevent a false-negative caused by a torn write between the two reads.

```python
import struct, sys

MAGIC   = 0xFADE5AFE
OFFSET  = 0x20007F00 - 0x20000000   # relative to a dump starting at 0x20000000

with open(sys.argv[1], "rb") as f:
    raw = f.read()[OFFSET : OFFSET + 32]

fields = struct.unpack_from("<8I", raw)   # little-endian; see note above
names  = ("magic", "version", "pc", "insn_count",
          "last_opcode", "tick_ms", "test_value", "checksum")
data   = dict(zip(names, fields))

if data["magic"] != MAGIC:
    print("INVALID — no magic word at expected offset")
else:
    xor = 0
    for k in names[:-1]:
        xor ^= data[k]
    ok = "OK" if xor == data["checksum"] else "BAD CHECKSUM"
    print(f"{ok}  pc=0x{data['pc']:08x}  insn={data['insn_count']}"
          f"  tick={data['tick_ms']} ms")
```

### Pattern 2 — ring-buffer event log (C, survives soft reset)

A ring buffer in a `.noinit` section retains events across a watchdog or
`NVIC_SystemReset()` call. You can retrieve the crash log on the next boot or
from a post-mortem dump.

Define the storage section in your linker script (see below), then use the
ring API. The minimal header surface is:

```c
/* blackbox_ring.h — minimum public API */
#include <stdint.h>
#include <stdbool.h>

void blackbox_init(void);
bool blackbox_record(uint8_t vm_id, uint16_t event_id, uint32_t timestamp_ms,
                     uint32_t pc, uint32_t error_code,
                     const uint8_t *payload, uint8_t payload_len);
bool blackbox_snapshot_tick(uint8_t vm_id, uint32_t timestamp_ms);
void blackbox_record_fault(uint8_t vm_id, uint16_t event_id,
                           uint32_t timestamp_ms, uint32_t pc,
                           uint32_t error_code);
```

```c
/* main.c excerpt */
#include "blackbox_ring.h"

int main(void) {
    HAL_Init();
    SystemClock_Config();

    blackbox_init();   /* no-op if magic is intact; zeroes if first boot */

    blackbox_record(0 /* vm_id */, BLACKBOX_EVENT_BOOT,
                    HAL_GetTick(), 0 /* pc */, 0 /* error */,
                    NULL, 0);

    while (1) {
        uint32_t pc = vm_step();          /* your execution loop */
        uint32_t tick = HAL_GetTick();

        blackbox_snapshot_tick(0, tick);  /* records every 250 ms */

        if (vm_faulted()) {
            blackbox_record_fault(0, BLACKBOX_EVENT_CRASH, tick, pc,
                                  vm_last_error());
            NVIC_SystemReset();
        }
    }
}
```

On the next boot `blackbox_init()` sees the intact magic word and leaves the
ring untouched. Dump the RAM region containing `g_blackbox_storage` and read
the events offline.

#### Linker script fragment

Add a `.noinit.blackbox` output section **before** `.bss` so the storage is
never zeroed at startup:

```ld
/* memory.ld — add inside SECTIONS { } before .bss */

.noinit.blackbox (NOLOAD) :
{
    . = ALIGN(4);
    KEEP(*(.noinit.blackbox))
    . = ALIGN(4);
} > RAM

/* optional: export symbol so GDB can find the struct by name */
blackbox_storage_start = ADDR(.noinit.blackbox);
```

Mark the storage variable with the matching section attribute:

```c
/* blackbox_ring.c */
__attribute__((section(".noinit.blackbox")))
static blackbox_storage_t g_blackbox_storage;
```

#### CRC-validated event record

Each event carries a CRC-32 so the dump parser can detect torn writes or
memory corruption. The struct uses `__attribute__((packed))` to eliminate
compiler-inserted padding; validate the layout with a size assert before
integrating:

```c
typedef struct __attribute__((packed)) {
    uint32_t timestamp_ms;
    uint32_t pc;
    uint32_t error_code;
    uint32_t seq;
    uint16_t event_id;
    uint8_t  vm_id;
    uint8_t  payload_len;
    uint8_t  payload[16];
    uint32_t crc32;          /* CRC-32 over all fields above */
} blackbox_event_t;

/* 4+4+4+4+2+1+1+16+4 = 40 bytes */
_Static_assert(sizeof(blackbox_event_t) == 40,
               "blackbox_event_t layout changed — update parser");
```

### Pattern 3 — C++ observer

If your execution loop exposes a `ITelemetryObserver` interface you can attach
a `BlackboxObserver` that forwards each instruction to the telemetry struct
without coupling the VM to the blackbox directly:

```cpp
/* main.cpp excerpt */
#include "blackbox_observer.h"   /* telemetry_t-backed observer */

int main() {
    BlackboxObserver observer;   /* creates and owns the blackbox instance */
    MyVM vm;
    vm.attach_observer(&observer);

    vm.run();

    /* telemetry is now live at TELEMETRY_BASE_ADDR; dump it with:
     *
     *   probe_blackbox_export out=/tmp/snap.bin
     *     start_addr=0x20000000 end_addr=0x20008000
     *
     * then read observer.get_blackbox() fields offline. */
    return 0;
}
```

```cpp
/* blackbox_observer.h */
#include "blackbox_telemetry.h"   /* C API — telemetry_init / telemetry_update */
#include <cstdint>

struct ITelemetryObserver {
    virtual void on_instruction_executed(uint32_t pc,
                                         uint8_t opcode,
                                         uint32_t operand) = 0;
    virtual void on_execution_complete(uint32_t total_instructions,
                                       uint32_t execution_time_ms) = 0;
    virtual void on_vm_reset() = 0;
    virtual ~ITelemetryObserver() = default;
};

class BlackboxObserver : public ITelemetryObserver {
public:
    BlackboxObserver() { telemetry_init(); }

    void on_instruction_executed(uint32_t pc,
                                 uint8_t  opcode,
                                 uint32_t operand) override {
        /* tick omitted per-instruction — HAL_GetTick() costs ~1 µs/call
         * on Cortex-M; sample it in on_execution_complete instead */
        telemetry_update(pc, operand,
                         static_cast<uint32_t>(opcode),
                         /* tick_ms */ 0);
    }

    void on_execution_complete(uint32_t total, uint32_t ms) override {
        /* pc = 0xFFFFFFFE is a reserved sentinel meaning "run complete";
         * it is never a valid Thumb instruction address (bit 0 clear,
         * top nibble 0xF reserved), so post-mortem tooling can distinguish
         * this record from a real fault PC */
        telemetry_update(0xFFFFFFFEU, total, ms, ms);
    }

    void on_vm_reset() override {
        telemetry_update(0, 0, 0, 0);
    }

    /* deleted — telemetry lives at a fixed RAM address; copies are meaningless */
    BlackboxObserver(const BlackboxObserver&)            = delete;
    BlackboxObserver& operator=(const BlackboxObserver&) = delete;
};
```

### GDB inspection without a full dump

If you have an active session you can inspect the struct in-place before
committing to a full export:

```
(gdb) x/8xw 0x20007F00
(gdb) print *(telemetry_t*)0x20007F00
(gdb) print blackbox_storage_start   /* if you exported the linker symbol */
```

---

## Questions and feedback

If something in this tutorial doesn't work for your target or toolchain, feel
free to [open an issue](https://github.com/cms-pm/brontes-probe-mcp/issues).
Include your MCU family, toolchain version, and the output you're seeing.
