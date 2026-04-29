# Modbus Logger & Grapher

A Tkinter-based Modbus TCP client that polls coils and holding registers from any Modbus device, logs everything to timestamped CSV files, and renders live Matplotlib charts of the active signals. Built as a lightweight companion tool for OT/ICS lab work, baselining, and field troubleshooting.

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Protocol](https://img.shields.io/badge/protocol-Modbus%20TCP-green)
![Use](https://img.shields.io/badge/use-logging%20%2F%20analysis-orange)
![Status](https://img.shields.io/badge/status-active-brightgreen)

---

## Overview

Point this tool at any Modbus TCP server — a real PLC, an HMI, a soft-PLC, or a simulator — and it will:

1. Poll a configurable number of coils and holding registers at a configurable interval.
2. Append every poll cycle to a CSV file in `modbus_logs/`, rotating to a fresh file every hour.
3. Plot every coil and register that has shown a non-zero value as its own subplot, refreshed every cycle.

It pairs naturally with the [Simple HVAC Simulator](#) (or any other Modbus TCP target) for hands-on practice — start the simulator, point this tool at `127.0.0.1:502`, and you've got a full lab loop: simulated PLC → live polling → CSV evidence → visual analysis.

---

## Features

- **Generic Modbus TCP client** — works against any device that speaks vanilla Modbus TCP
- **Configurable polling** — IP, port, polling interval, coil count, register count, all set from the GUI
- **CSV logging with hourly rotation** — one tidy file per hour, ISO 8601 timestamps, headers included
- **Excel-friendly** — gracefully retries writes if the CSV is open in another program rather than crashing
- **Dynamic charting** — only signals that have actually changed get plotted, so you're not staring at flat lines for unused points
- **Threaded polling** — the GUI stays responsive while the logger runs in the background
- **Clean shutdown** — Stop button gracefully closes the Modbus client and joins the worker thread

---

## Prerequisites

- Python 3.8 or newer
- `pymodbus` (3.x branch — the script uses the modern `pymodbus.client.ModbusTcpClient` API)
- `matplotlib`
- `tkinter` — bundled with most Python distributions; on some Linux installs you may need `sudo apt install python3-tk`

The remaining imports (`os`, `csv`, `time`, `datetime`, `threading`) are all standard library.

---

## Installation

```bash
# Clone the repo
git clone https://github.com/<your-username>/modbus-logger-grapher.git
cd modbus-logger-grapher

# (Recommended) create a virtual environment
python -m venv venv
source venv/bin/activate          # Linux/macOS
venv\Scripts\activate             # Windows

# Install dependencies
pip install pymodbus matplotlib
```

---

## Usage

```bash
python modbus_2_gui.py
```

The GUI opens with sensible defaults you can override:

| Field | Default | Notes |
|-------|---------|-------|
| PLC IP | `127.0.0.1` | Target Modbus TCP server |
| Port | `502` | Standard Modbus TCP port |
| Polling (s) | `1` | Decimal values are fine (e.g., `0.5`) |
| Coils | `10` | Number of coils to poll, starting at address 0 |
| Registers | `10` | Number of holding registers to poll, starting at address 0 |

Click **Start Logging** to begin. The chart area populates as soon as any polled value goes non-zero. Click **Stop** to end the session cleanly. CSV files keep accumulating in `modbus_logs/` between sessions — they are never overwritten.

> **Note:** Polling starts at Modbus address `0`. If your target uses 1-based addressing in its documentation (most do), the first coil/register the tool reads is what your docs call coil/register #1.

---

## CSV Output Format

Files are written to `modbus_logs/modbus_data_YYYY-MM-DD_HH-MM-SS.csv` with this header layout:

```
timestamp, coil_1, coil_2, ..., coil_N, reg_1, reg_2, ..., reg_N
```

- `timestamp` — ISO 8601 string with microseconds, generated per poll cycle
- `coil_X` — `0` or `1`
- `reg_X` — 16-bit unsigned integer (0–65535) as returned by the device

A new file is created automatically every hour. Closing and reopening the app also creates a new file — there's no append-to-existing-file behavior, which keeps each session cleanly separated.

---

## Charting Behavior

The plotting logic is intentionally minimalist:

- A signal only gets a subplot once it has shown at least one non-zero value across the session — this keeps the screen clean when you're polling 10 coils but only 3 are wired to anything interesting.
- Coils render in red; holding registers render in blue.
- All subplots share the X axis, so timing relationships between signals are easy to read.
- The chart redraws on every poll cycle, so very fast polling intervals on weak hardware may feel sluggish — bump the interval up to `0.5s` or `1s` if needed.

---

## Lab Use Cases

A few ways this tool earns its keep in an OT/ICS context:

**Baselining**
- Capture a clean, multi-hour baseline of a device under normal operating conditions
- Use the resulting CSV as a reference for anomaly detection or detection rule tuning

**Pentest evidence collection**
- Run alongside an exercise to capture before/during/after data when manipulating registers
- Rotate logs hourly means you have neat per-hour evidence chunks for reporting

**Training and demos**
- Show a live audience exactly what's happening on the wire when an HMI writes a setpoint or flips a coil
- Pair with the Simple HVAC Simulator for a self-contained classroom demo with no real iron

**Field troubleshooting**
- Point at a flaky PLC for a few hours and review the CSV to spot intermittent register flapping
- Eyeball the live charts during commissioning to confirm a new I/O point is wired correctly

---

## Architecture

```
┌──────────────────────────────────────────────┐
│              Python Process                  │
│                                              │
│  ┌────────────────┐   ┌────────────────────┐ │
│  │  Tkinter GUI   │   │  ModbusLogger      │ │
│  │  (main thread) │◄──┤  (worker thread)   │ │
│  │                │   │  pymodbus client   │ │
│  │  Matplotlib    │   └─────────┬──────────┘ │
│  │  canvas        │             │            │
│  └────────────────┘             │            │
│                                 ▼            │
│                         ┌──────────────┐     │
│                         │  CSV writer  │     │
│                         │  (hourly     │     │
│                         │   rotation)  │     │
│                         └──────────────┘     │
└──────────────────────────────────────────────┘
                ▲
                │ Modbus TCP
                ▼
       ┌─────────────────┐
       │  Modbus device  │
       │  (PLC / sim /   │
       │   soft-PLC)     │
       └─────────────────┘
```

The polling thread reads, writes the CSV row, and calls back into the GUI to redraw the chart. The main thread does nothing but render the UI, so heavy charting won't block I/O.

---

## Known Limitations

- **Holding registers only** — input registers (FC 4) and discrete inputs (FC 2) aren't read. If your target uses those, extend `ModbusLogger.run()` accordingly.
- **Starts at address 0** — there's no UI field for the starting address yet. Edit the `start_addr=0` argument in `start_logging()` if you need a different offset.
- **Unsigned 16-bit only** — registers are stored as raw unsigned integers. Signed values, 32-bit floats, or strings will need post-processing.
- **No authentication** — Modbus TCP doesn't have any. If your target requires it (some gateways do), add it to the client setup.
- **GUI redraw on every poll** — at sub-100ms polling intervals on slow hardware, the chart may lag. Logging continues regardless.

---

## Contributing

Issues and PRs welcome. A few additions that would meaningfully extend this:

- Configurable starting address and function code selector
- Signed integer, 32-bit float, and string register decoding
- Per-signal toggles in the GUI to manually show/hide subplots
- Save chart as PNG / export current view
- Connection retry/backoff for unstable links

---

## Disclaimer

This is a generic Modbus TCP client. Modbus has no built-in authentication or authorization, and aggressive polling can affect device performance on real production systems. Only point this tool at devices you own or have explicit written authorization to read.

You are solely responsible for how you use this code.

---

## License

Add a license file (MIT, Apache 2.0, or similar) to declare reuse terms. Until then, all rights reserved by default.

---

## Author

Built as a hands-on companion tool for OT/ICS cybersecurity training and Modbus lab work.
