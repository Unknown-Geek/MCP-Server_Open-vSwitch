# Lightweight MCP Server in C

This repository contains a lightweight Model Context Protocol (MCP) server integrated directly into `ovs-vswitchd`.

---

## Module 1 & 2 - Basic MCP Server Integration

### Files Added
- `vswitchd/mcp_server.c`
- `vswitchd/mcp_server.h`

### Files Modified
- `vswitchd/ovs-vswitchd.c`
  - Called `mcp_server_init()` during startup.
  - Called `mcp_server_run()` inside the main loop.
  - Called `mcp_server_close()` during shutdown.
- `vswitchd/automake.mk`
  - Added `mcp_server.c` to build sources.

### Functionality
- **Server Port:** `8080`
- **Endpoint:** `POST /mcp`
- **Response:** `{"status": "ok"}`

---

## Module 3 - MCP Tool Routing and Mock Handlers

### Files Modified
- `vswitchd/mcp_server.c`
  - Added HTTP request parsing and JSON dispatcher so MCP calls can route to tool handlers.
  - Added non-blocking socket handling and `mcp_server_wait()` polling so `ovs-vswitchd` stays responsive.
  - Added `Content-Length` validation and request-size checks so malformed or incomplete requests are handled safely.
  - Switched startup and shutdown logs to OVS `VLOG` style.
- `vswitchd/mcp_server.h`
  - Declared `mcp_server_wait()` for poll loop wakeups.
- `vswitchd/ovs-vswitchd.c`
  - Hooked `mcp_server_wait()` into the wait phase.
- `vswitchd/bridge.c` / `vswitchd/bridge.h`
  - Created initial mock handlers for `switch.get_ports`, `switch.get_flows`, and `switch.get_port_stats` returning hardcoded/static JSON data.

### Functionality
- **Supported MCP Tools:** `switch.get_ports`, `switch.get_flows`, `switch.get_port_stats`
- **Request Safety:** method and path validation, JSON checks, max size guard (64KB).

---

## Module 4 - Connect MCP to OVS Internals with Real Data

### Files Modified
- `vswitchd/bridge.c`
  - Replaced the mock code with real-data retrieval from OVS structures:
    - `switch.get_ports`: Traverses the live `all_bridges` list to construct active bridges, ports, and interface lists.
    - `switch.get_flows`: Queries active OpenFlow engine state using `ofproto_get_all_flows()`.
    - `switch.get_port_stats`: Queries interface statistics via `netdev_get_stats()`.

---

## Module 5 - SET Operations (VLAN and Port Link State)

### Files Modified
- `vswitchd/bridge.h` / `vswitchd/bridge.c`
  - Implemented `bridge_mcp_set_vlan()` for VLAN tags.
  - Implemented `bridge_mcp_set_port_state()` for administrative port up/down flags.
- `vswitchd/mcp_server.c`
  - Registered `switch.set_vlan` and `switch.set_port_state` tools.
- `lib/ovsdb-idl.c` / `lib/ovsdb-idl.h`
  - Created `ovsdb_idl_disable_verify_write_only()` and `ovsdb_idl_verify_write_only()` helpers to bypass write verification constraints on read/write columns.

### Functionality

1. **VLAN Configuration (`switch.set_vlan`)**
   - Arguments: `{"bridge": "<bridge>", "port": "<port>", "vlan": <vlan_val>}`
   - Sets the access VLAN tag (0-4095) using a synchronous OVSDB transaction commit (`ovsdb_idl_txn_commit_block`). This blocks until the transaction is acknowledged by `ovsdb-server`, preventing race conditions with immediate database reads. Setting `vlan` to `0` clears the tag.

2. **Port State Configuration (`switch.set_port_state`)**
   - Arguments: `{"bridge": "<bridge>", "port": "<port>", "enabled": <bool>}`
   - Administratively enables or disables the interface link flags (UP/DOWN) synchronously using `netdev_turn_flags_on()` and `netdev_turn_flags_off()`.

---

## Module 6 - LLM Integration (Google Gemini API)

This module integrates the Google Gemini API with the OVS MCP server, enabling natural language command execution (e.g. *"Show ports"*, *"Set VLAN on br0 to 100"*).

### Files Added
- `mcp_gemini_client.py` (Python LLM client with local `.env` and function calling tool integration)
- `.env.example` (Template environment file)

### Files Modified
- `.gitignore` (Added `.env` to prevent committing secrets)
- `Makefile.am` (Registered the client and added a custom `.PHONY: chat` build target)
- `build.sh` (Added automatic check/installation for `python3-pip` and `google-genai` library)

### Functionality
- **API Environment Loader:** Reads model name (`GEMINI_MODEL`) and API key (`GEMINI_API_KEY`) from local `.env`.
- **Tool Mapping:** Connects Gemini's function calling mechanism to target OVS MCP REST API tools (`switch.get_ports`, `switch.get_flows`, `switch.get_port_stats`, `switch.set_vlan`, `switch.set_port_state`).

---

## Setup and Run

### Build OVS

```bash
./boot.sh
./configure
make -j"$(nproc)"
sudo make install
```

### Start OVS

Start database server:
```bash
sudo ovsdb-server \
  --remote=punix:/usr/local/var/run/openvswitch/db.sock \
  --remote=db:Open_vSwitch,Open_vSwitch,manager_options \
  --pidfile --detach
```

Initialize DB:
```bash
sudo ovs-vsctl --no-wait init
```

Start switch daemon:
```bash
sudo ovs-vswitchd --pidfile --detach
```

### Testing the MCP API

To set the VLAN tag to `100`:
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"id": "1", "tool": "switch.set_vlan", "arguments": {"bridge": "br0", "port": "br0", "vlan": 100}}' \
  http://localhost:8080/mcp
```

Verify tag is set:
```bash
sudo ovs-vsctl get port br0 tag
```

### AI Assistant Chat

Configure your API Key and choice of model inside `.env`:
```env
GEMINI_API_KEY="AQ.your-key-here"
GEMINI_MODEL="gemini-3.1-flash-lite"
```

Start the interactive chat interface:
```bash
make chat
```
