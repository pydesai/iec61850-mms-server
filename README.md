# IEC 61850 MMS Simulator

A spec-compliant **IEC 61850 MMS (Manufacturing Message Specification) protocol server simulator** with an enterprise-grade web UI. Built on [libIEC61850](https://github.com/mz-automation/libiec61850) — the most widely adopted open-source IEC 61850 implementation used in production substations worldwide.

---

## Overview

This simulator lets you spin up a fully functional IEC 61850 MMS server in a single Docker command. It ships with a default model of **20 IEDs and 14,000+ data attributes** covering protection, measurement, and control logical nodes — all simulating realistic sinusoidal values in real time.

Use it to:
- Test MMS client implementations against a real protocol server
- Develop and validate IEC 61850 integration code
- Learn the IEC 61850 data model interactively
- Demo SCADA and substation automation products

![Dashboard Screenshot](docs/dashboard.png)

---

## Features

| Feature | Details |
|---|---|
| **MMS Protocol** | Full IEC 61850-7-2 ACSI via MMS (ISO 9506), port 102 |
| **Data Operations** | Read, Write, Control (Direct Operate, Select-Before-Operate), Reporting (buffered + unbuffered RCBs) |
| **5000+ Data Points** | 20 IEDs × protection + measurement LDs with MMXU, XCBR, XSWI, PDIS, PTOC, MSQI, MSTA logical nodes |
| **SCL File Upload** | Load any ICD / CID / SCD substation configuration file to replace the default model |
| **Live Simulation** | All MX (measurement) attributes update every 2 seconds with sinusoidal variation |
| **Multiple Clients** | Up to 50 simultaneous MMS clients (configurable); live connection count on UI |
| **Authentication** | No auth / ACSE password / TLS (transport proxy) |
| **Interface Binding** | Bind to any network interface or `0.0.0.0` for all |
| **Port Configuration** | Default port 102; change from UI without restarting manually |
| **Log Viewer** | Real-time color-coded terminal (ERROR / WARN / INFO / DEBUG) with pause, filter, download |
| **Enterprise UI** | React 18 + Ant Design; responsive layout with sidebar navigation |

---

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) 24+
- [Docker Compose](https://docs.docker.com/compose/install/) v2+

### Run

```bash
git clone https://github.com/pydesai/iec61850-mms-server.git
cd iec61850-mms-server
docker-compose up --build
```

| Service | URL / Address |
|---|---|
| **Web UI** | http://localhost:8080 |
| **MMS Server** | `localhost:102` |
| **REST API** | http://localhost:8000/docs |

> **First boot** takes ~60 seconds to build the Docker images and load the default 14,000-attribute model.

### Stop

```bash
docker-compose down
```

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Docker Compose                      │
│                                                      │
│  ┌──────────────────┐      ┌──────────────────────┐ │
│  │   frontend       │      │   backend            │ │
│  │   nginx:1.27     │ ───▶ │   Python 3.12        │ │
│  │   port 8080      │      │   FastAPI + uvicorn   │ │
│  │                  │      │   port 8000           │ │
│  │  React 18        │      │                      │ │
│  │  Ant Design      │      │  pyiec61850          │ │
│  │  xterm.js        │      │  (libIEC61850 v1.5)  │ │
│  └──────────────────┘      │   port 102  ◀── MMS  │ │
│                             └──────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

- **nginx** serves the React SPA and proxies `/api` and `/ws` to FastAPI
- **FastAPI** (single worker) wraps the pyiec61850 MMS server and exposes REST + WebSocket endpoints
- **pyiec61850** is the Python binding for libIEC61850 — a mature C library implementing the full MMS stack
- **WebSocket** pushes real-time log entries, server status, and connection count changes to the UI

---

## Default Data Model

The server starts with a built-in IEC 61850 model — no SCL file needed.

```
20 IEDs:  IED01 … IED20
  Each IED
  ├── {IED}PROT  (Protection Logical Device)
  │   ├── LLN0   — Logical Node Zero (RCBs, datasets)
  │   ├── XCBR1  — Circuit Breaker (SBO control, Pos, OpCnt, BlkOpn, BlkCls)
  │   ├── XSWI1  — Disconnector Switch (SBO control, Pos, OpCnt)
  │   ├── PDIS1  — Distance Protection (Op, Str, Z, RStr)
  │   ├── PTOC1  — Overcurrent Protection (Op, Str, StrVal, StrMul)
  │   └── MMXU1  — Measurements (TotW, TotVAr, TotVA, TotPF, Hz, PhV, A, W, VAr, VA, PF)
  │
  └── {IED}MEAS  (Measurement Logical Device)
      ├── LLN0   — Logical Node Zero
      ├── MMXU1  — Three-Phase Measurements Ch1
      ├── MMXU2  — Three-Phase Measurements Ch2
      ├── MMXU3  — Three-Phase Measurements Ch3
      ├── MSQI1  — Sequence Measurements (SeqA, SeqV)
      └── MSTA1  — Statistical Measurements (AvAmps, AvPPV, AvVolts, AvWatts, energy totals)
```

**Per MMXU logical node:**
- 5 scalar MV objects: `TotW`, `TotVAr`, `TotVA`, `TotPF`, `Hz`
- 6 three-phase WYE objects: `PhV`, `A`, `W`, `VAr`, `VA`, `PF` — each with `phsA`, `phsB`, `phsC` sub-attributes

Each logical device has a buffered RCB (`brcb01`) and an unbuffered RCB (`urcb01`) on LLN0, with a dataset covering the key MX values.

---

## Web UI Guide

### Dashboard

The landing page shows the overall server health at a glance:

- **MMS Server card** — current status (RUNNING / STOPPED), listening interface and port, uptime, model name. Use **Start** / **Stop** buttons to control the server.
- **Active Connections** — live count of connected MMS clients, updated via WebSocket.
- **Data Model** — total number of indexed data attributes.
- **SCL Configuration** — drag-and-drop upload of a custom SCL file.
- **Recent Events** — last 8 log entries for quick diagnostics.

### Data Browser

Browse the entire IEC 61850 object model:

1. **Left panel** — device tree showing all Logical Devices and their Logical Nodes. Click any node to filter the table.
2. **Right table** — paginated list of data attributes (100 per page) with:
   - Full object reference (e.g., `IED01PROT/MMXU1.TotW.mag.f`)
   - Functional Constraint (MX, ST, CF, SP, CO …) color-coded
   - Data type (FLOAT32, BOOLEAN, INT32 …)
   - Current value (refreshes every 5 seconds)
   - **Write** button — opens an inline modal to write a new value

3. **Search bar** — filter by reference string across all 14,000+ attributes.

### Connections

Shows the count of currently connected MMS clients in real time. Updates instantly via WebSocket when clients connect or disconnect.

### Logs

Full-screen terminal powered by xterm.js:

- **Color coding** — `ERROR` red, `WARN` yellow, `INFO` cyan, `DEBUG` gray
- **Level filter** — show only ERROR / WARN / INFO / DEBUG / All
- **Pause / Resume** — freeze the log display while inspecting entries
- **Download** — export the current log buffer as a `.log` file
- **Clear** — wipe the in-memory log buffer

### Settings

Configure the MMS server (changes take effect immediately; the server restarts automatically):

| Setting | Description |
|---|---|
| **Network Interface** | Dropdown of all host interfaces with their IP addresses. Select `0.0.0.0` to listen on all interfaces. |
| **MMS Port** | Default `102`. Change to any port (e.g., `10102`) if you don't have root/capability access. |
| **Max Connections** | Maximum simultaneous MMS clients (1–200, default 50). |
| **Authentication Mode** | See [Authentication](#authentication) below. |

---

## Authentication

### No Authentication (default)

Any MMS client can connect with no credentials.

### Password (ACSE)

Application-layer authentication per IEC 61850 MMS ACSE. The client must supply the correct password in the AARQ PDU.

1. Select **Password** in Settings
2. Enter a password (username is optional)
3. Click **Save & Restart Server**

Configure your MMS client to send the password on connect. With libIEC61850's `mms-client`:
```bash
mms-client localhost 102 -a password:<your-password>
```

### TLS

Transport-layer encryption. Certificates are uploaded via the Settings page and applied at the nginx proxy.

> **Note:** TLS terminates at the nginx proxy layer, not at the MMS ACSE layer. This protects the connection in transit but is not strictly compliant with IEC 62351-4 which specifies TLS at the MMS transport level. Full MMS-layer TLS requires building libIEC61850 from source with mbedTLS support (`-DBUILD_MBEDTLS=ON`).

**To enable TLS:**
1. Select **TLS** in Settings
2. Upload your PEM certificate and private key
3. Click **Save & Restart Server**

---

## SCL File Upload

The simulator can load any valid IEC 61850-6 SCL file to replace the default model.

**Supported formats:** `.icd`, `.cid`, `.scd`, `.iid`

**To load a custom model:**
1. Go to **Dashboard → SCL Configuration**
2. Drag-and-drop or click to upload your SCL file
3. The file is validated (XML parse + IEC 61850 structure check)
4. Click **Load into Server** — the server briefly restarts with the new model
5. The Data Browser immediately reflects the new device tree

**What the SCL parser handles:**
- `DataTypeTemplates` → `LNodeType`, `DOType`, `DAType` resolution
- All standard CDCs: MV, WYE, CMV, SPS, DPS, INS, ENS, BCR, DPC, SPC, INC, ACD, ACT, SPG, ING, ASG, LPL, DPL, DEL, BSC, ISC, SAV
- Multiple IEDs and Access Points in a single SCD file
- Custom (non-standard CDC) data objects via fallback `DataObject_create()`

---

## Connecting an MMS Client

Any standard IEC 61850 MMS client can connect. Here are some options:

### libIEC61850 `mms-client` (command line)

The libIEC61850 project ships a command-line client:

```bash
# Clone and build libIEC61850
git clone https://github.com/mz-automation/libiec61850
cd libIEC61850 && mkdir build && cd build
cmake .. && make -j4

# Connect to the simulator
./mms_client_example localhost 102

# Read a specific value
./read_all_values localhost 102
```

### IEC 61850 Browser (GUI)

[IEC 61850 Browser](https://www.mz-automation.de/iec-61850-tools/) by MZ Automation provides a GUI for browsing data objects, reading values, and testing control.

### OpenMUC j60870 / IEC61850bean

```java
// Java example using IEC61850bean
IedConnection con = ClientSap.connect("localhost", 102);
FcModelNode node = (FcModelNode) con.getModelNode("IED01PROT/MMXU1.TotW.mag.f");
con.setFloat(node, 1234.5f);
```

---

## REST API Reference

The FastAPI backend exposes a full REST API. Interactive docs at **http://localhost:8000/docs**.

### Server Control

```
GET  /api/server/status        Server status, connection count, uptime, DA count
POST /api/server/start         Start MMS server with current config
POST /api/server/stop          Stop MMS server
GET  /api/server/interfaces    List network interfaces with IP addresses
```

### SCL Management

```
POST   /api/scl/upload          Upload SCL file (multipart form, max 50 MB)
GET    /api/scl/files           List uploaded SCL files
POST   /api/scl/load/{filename} Stop, rebuild model from SCL, restart
DELETE /api/scl/{filename}      Delete an uploaded SCL file
```

### Data Points

```
GET  /api/devices                    Full model tree (IEDs → LDs → LNs)
GET  /api/datapoints                 Paginated list of all data attributes + values
                                     Query: page, page_size, search, ld, ln
GET  /api/datapoints/{ref}           Read single data attribute value
PUT  /api/datapoints/{ref}           Write value  {"value": 230.5, "value_type": "FLOAT32"}
POST /api/datapoints/{ref}/operate   Control operate/select  {"action": "operate", "value": true}
```

### Logs

```
GET    /api/logs     Retrieve logs  Query: level, limit, since
DELETE /api/logs     Clear log buffer
```

### Configuration

```
GET  /api/config              Current server configuration
PUT  /api/config              Update config (triggers server restart)
POST /api/config/tls/upload   Upload TLS certificate + private key
```

### WebSocket

Connect to `ws://localhost:8080/ws` for real-time push events:

```json
// Server status update
{ "type": "server_status", "data": { "running": true, "connections": 3, "uptime": 142.5 } }

// New log entry
{ "type": "log_entry", "data": { "level": "INFO", "message": "MMS client connected", "timestamp": "2026-04-23T10:15:30.123Z" } }

// Keepalive
{ "type": "ping" }
```

Send `{ "type": "ping" }` to keep the connection alive.

---

## Configuration Reference

Default configuration (editable via Settings UI or `PUT /api/config`):

| Parameter | Default | Description |
|---|---|---|
| `port` | `102` | MMS server TCP port |
| `interface` | `0.0.0.0` | Bind address (`0.0.0.0` = all interfaces) |
| `auth_mode` | `none` | `none` / `password` / `tls` |
| `auth_username` | `null` | ACSE username (optional with password mode) |
| `auth_password` | `null` | ACSE password |
| `max_connections` | `50` | Max simultaneous MMS clients |
| `report_buffer_size` | `65536` | Buffered RCB buffer size in bytes |

---

## Port 102 Access

Port 102 is a privileged port (< 1024). The Docker container is configured with `NET_BIND_SERVICE` capability so it can bind without running as root.

**On macOS / Docker Desktop:** Port 102 binding works via Docker Desktop's port mapping — no additional setup needed.

**On Linux (host network mode):** If you run without Docker, you need either:
```bash
# Option 1: Run as root
sudo python3 -m uvicorn main:app ...

# Option 2: Grant capability to the Python binary
sudo setcap cap_net_bind_service=+ep $(which python3)

# Option 3: Use a higher port (e.g., 10102) — no privilege needed
```

---

## Project Structure

```
iec61850-mms-server/
├── backend/
│   ├── main.py                    FastAPI application + lifespan (auto-starts default model)
│   ├── config.py                  Pydantic ServerConfig model
│   ├── requirements.txt
│   ├── iec61850/
│   │   ├── server.py              MmsServer class — start/stop/read/write/poll/simulate
│   │   ├── default_model.py       Builds 20-IED model via pyiec61850 dynamic API
│   │   ├── scl_parser.py          IEC 61850-6 SCL XML parser (stdlib xml.etree)
│   │   ├── model_builder.py       Converts ParsedSCL → pyiec61850 IedModel
│   │   └── auth.py                ACSE password auth via ctypes
│   ├── api/
│   │   ├── routes/
│   │   │   ├── server_routes.py   /api/server/*
│   │   │   ├── scl_routes.py      /api/scl/*
│   │   │   ├── datapoints_routes.py /api/datapoints/*
│   │   │   ├── connections_routes.py /api/connections
│   │   │   ├── logs_routes.py     /api/logs
│   │   │   └── config_routes.py   /api/config/*
│   │   └── websocket.py           WebSocket manager + endpoint
│   └── state/
│       ├── app_state.py           Shared singleton (IedServer, model, da_cache, config)
│       └── log_buffer.py          Thread-safe ring buffer with asyncio fan-out
│
├── frontend/
│   └── src/
│       ├── App.tsx                Root layout + router
│       ├── pages/
│       │   ├── Dashboard.tsx      Server control + overview
│       │   ├── DataBrowser.tsx    IED tree + data attribute table
│       │   ├── Connections.tsx    Active MMS clients
│       │   ├── Logs.tsx           xterm.js log terminal
│       │   └── Settings.tsx       Server configuration
│       ├── api/                   Typed fetch wrappers
│       ├── store/serverStore.ts   Zustand global state
│       └── hooks/useWebSocket.ts  Auto-reconnecting WebSocket
│
├── docker/
│   ├── Dockerfile.backend         python:3.12-slim + pyiec61850
│   ├── Dockerfile.frontend        node:20-alpine build → nginx:1.27-alpine
│   └── nginx.conf                 SPA routing + API + WebSocket proxy
│
├── docker-compose.yml
└── sample_scl/
    └── default_5000.icd           Reference ICD file showing the full data model schema
```

---

## Technical Notes

### Thread Safety

libIEC61850 runs its own internal server thread. All Python-thread access to data attributes must be wrapped with:

```python
IedServer_lockDataModel(server)
try:
    IedServer_updateFloatAttributeValue(server, da, value)
finally:
    IedServer_unlockDataModel(server)
```

Control handler callbacks (`ControlHandlerForPython.trigger()`) run inside libIEC61850's internal thread and must **not** call `lockDataModel` — doing so causes a deadlock.

### Single Worker

uvicorn is configured with `--workers 1`. pyiec61850's `IedServer` is a C singleton that cannot be safely shared across forked processes.

### Value Simulation

All MX (measurement) data attributes are updated every 2 seconds with a sinusoidal signal:

```
value = base + amplitude × sin(t + phase_offset) + noise
```

Each data point has a unique phase offset derived from its reference string hash, so IED01 and IED20 show meaningfully different values at any given time.

**Simulation profiles:**

| Data Object | Base Value | Amplitude |
|---|---|---|
| `PhV` (phase voltage) | 230 V | ±5 V |
| `A` (current) | 100 A | ±10 A |
| `TotW` (active power) | 5000 W | ±500 W |
| `TotVAr` (reactive power) | 1200 VAr | ±300 VAr |
| `Hz` (frequency) | 50 Hz | ±0.05 Hz |
| `TotPF` (power factor) | 0.95 | ±0.03 |

### Logging Limitation

Raw RX/TX PDU byte traces are not accessible through pyiec61850's SWIG interface. The log viewer shows:
- Server start/stop events
- MMS client connect/disconnect with connection count
- Data write events (reference + new value)
- Control operate events
- SCL load events and errors

Full PDU tracing (hex dumps of MMS PDUs) requires building libIEC61850 from source with a custom transport layer callback.

---

## Troubleshooting

**Server fails to start on port 102**

Port 102 requires the `NET_BIND_SERVICE` capability. In Docker this is set automatically. Outside Docker on Linux:
```bash
sudo setcap cap_net_bind_service=+ep $(which python3)
```
Or change the port to something above 1024 in Settings.

**`pyiec61850` not found on ARM (Apple Silicon)**

The prebuilt `pyiec61850==1.5.2a1` wheel is built for `manylinux_2_17_x86_64`. On ARM64 Docker hosts, enable `platform: linux/amd64` in `docker-compose.yml`:
```yaml
services:
  backend:
    platform: linux/amd64
```

**SCL file upload returns 422**

The SCL parser requires a valid `<DataTypeTemplates>` block with all referenced `LNodeType`, `DOType`, and `DAType` IDs present. Validate your SCL file with a tool like [SCLValidator](https://github.com/iec61850-validator) before uploading.

**MMS client cannot connect**

1. Confirm the server shows **RUNNING** in the Dashboard
2. Check the Logs page for bind errors — the port may be in use
3. Ensure your client targets the correct host IP (not `0.0.0.0`) and port
4. If authentication is enabled, confirm credentials match Settings

---

## License

This project is released under the **MIT License**.

The underlying libIEC61850 C library is licensed under **GPLv3**. The `pyiec61850` Python binding bundles a static copy of libIEC61850. Commercial use of libIEC61850 requires a separate commercial license from [MZ Automation](https://www.mz-automation.de/).

---

## References

- [IEC 61850 Standard](https://www.iec.ch/iec61850) — IEC 61850-7-2 ACSI, IEC 61850-8-1 MMS mapping, IEC 61850-6 SCL
- [libIEC61850](https://github.com/mz-automation/libiec61850) — open-source C implementation
- [IEC 62351](https://www.iec.ch/iec62351) — Security standards for power systems communication
- [ISO 9506](https://www.iso.org/standard/17283.html) — Manufacturing Message Specification (MMS)
