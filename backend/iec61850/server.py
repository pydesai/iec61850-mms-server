"""
MmsServer: thread-safe wrapper around pyiec61850 IedServer lifecycle.

Key threading rules (from libIEC61850 docs):
- IedServer_lockDataModel / IedServer_unlockDataModel required for all
  value reads/writes from Python threads.
- Control handler callbacks (ControlHandlerForPython.trigger) run inside
  libiec61850's internal thread — they must NOT call lock/unlock (deadlock).
- IedServer_start is synchronous — call from a thread pool, never the event loop.
"""
from __future__ import annotations
import asyncio
import math
import random
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import pyiec61850 as iec61850

from config import ServerConfig
from state.app_state import AppState
from state.log_buffer import LogBuffer
from iec61850.auth import install_password_authenticator

# Simulation value profiles: {do_name_keyword: (base, amplitude, unit)}
_SIM_PROFILES: dict[str, tuple[float, float]] = {
    "TotW":   (5000.0, 500.0),
    "TotVAr": (1200.0, 300.0),
    "TotVA":  (5200.0, 520.0),
    "TotPF":  (0.95,   0.03),
    "Hz":     (50.0,   0.05),
    "PhV":    (230.0,  5.0),
    "A":      (100.0,  10.0),
    "W":      (1500.0, 150.0),
    "VAr":    (400.0,  80.0),
    "VA":     (1600.0, 160.0),
    "PF":     (0.94,   0.03),
    "SeqA":   (100.0,  5.0),
    "SeqV":   (230.0,  3.0),
    "AvAmps": (95.0,   8.0),
    "AvPPV":  (398.0,  5.0),
    "AvVolts":(230.0,  4.0),
    "AvWatts":(4800.0, 480.0),
}


# ControlHandlerForPython is a SWIG director class that only exists when
# libIEC61850 is compiled from source with -DBUILD_PYTHON_BINDINGS=ON. The
# PyPI pyiec61850 wheel does NOT ship with it. We detect availability at
# import time and skip server-side control handler installation if missing.
# Control operations from clients are still accepted by libiec61850 itself;
# we just don't get a Python callback for each one. The API layer logs
# operate-requests via the /operate route handler instead.
_HAS_CONTROL_HANDLER = hasattr(iec61850, "ControlHandlerForPython")

if _HAS_CONTROL_HANDLER:
    class _ControlHandler(iec61850.ControlHandlerForPython):  # type: ignore[misc]
        def __init__(self, ref: str, log: LogBuffer):
            super().__init__()
            self._ref = ref
            self._log = log

        def trigger(self, action, test):
            self._log.append("INFO", f"Control: {self._ref} action={action} test={test}")
            return getattr(iec61850, "CONTROL_RESULT_OK", 0)
else:
    class _ControlHandler:  # noqa: D401 — stub placeholder
        """Stub used when pyiec61850 wheel does not expose the SWIG director."""
        def __init__(self, *args, **kwargs):  # pragma: no cover
            pass


class MmsServer:
    def __init__(self, app_state: AppState, log_buffer: LogBuffer) -> None:
        self._state = app_state
        self._log = log_buffer
        self._poll_stop = threading.Event()
        self._poll_thread: Optional[threading.Thread] = None
        self._sim_thread: Optional[threading.Thread] = None
        self._control_handlers: list = []

    # ------------------------------------------------------------------
    # Public API (called from FastAPI routes via asyncio.run_in_executor)
    # ------------------------------------------------------------------

    def start(
        self,
        model: Any,
        da_cache: dict[str, Any],
        config: ServerConfig,
    ) -> None:
        with self._state._lock:
            if self._state.ied_server is not None:
                raise RuntimeError("MMS server is already running")

            # Prefer the newer IedServerConfig API when available; fall back
            # to the simpler IedServer_create(model) constructor otherwise.
            server = None
            if hasattr(iec61850, "IedServerConfig_create"):
                try:
                    srv_config = iec61850.IedServerConfig_create()
                    if hasattr(iec61850, "IedServerConfig_setMaxMmsConnections"):
                        iec61850.IedServerConfig_setMaxMmsConnections(
                            srv_config, config.max_connections
                        )
                    if hasattr(iec61850, "IedServerConfig_setReportBufferSize"):
                        iec61850.IedServerConfig_setReportBufferSize(
                            srv_config, config.report_buffer_size
                        )
                    if hasattr(iec61850, "IedServer_createWithConfig"):
                        server = iec61850.IedServer_createWithConfig(model, None, srv_config)
                except Exception as exc:
                    self._log.append(
                        "WARN", f"IedServerConfig path failed, using simple create: {exc}"
                    )
                    server = None

            if server is None:
                server = iec61850.IedServer_create(model)

            if config.interface and config.interface != "0.0.0.0" and hasattr(
                iec61850, "IedServer_setLocalIpAddress"
            ):
                try:
                    iec61850.IedServer_setLocalIpAddress(server, config.interface)
                except Exception as exc:
                    self._log.append("WARN", f"setLocalIpAddress not supported: {exc}")

            # Write access policy — best-effort
            for fc_name in ("IEC61850_FC_SP", "IEC61850_FC_SV", "IEC61850_FC_CF"):
                if hasattr(iec61850, fc_name) and hasattr(iec61850, "ACCESS_POLICY_ALLOW"):
                    try:
                        iec61850.IedServer_setWriteAccessPolicy(
                            server,
                            getattr(iec61850, fc_name),
                            iec61850.ACCESS_POLICY_ALLOW,
                        )
                    except Exception:
                        pass

            if config.auth_mode == "password" and config.auth_password:
                try:
                    install_password_authenticator(server, config.auth_password)
                    self._log.append("INFO", "Password authentication enabled")
                except Exception as exc:
                    self._log.append("WARN", f"Password auth setup failed: {exc}")

            # Install control handlers for controllable data objects
            # (no-op when pyiec61850 wheel doesn't expose ControlHandlerForPython)
            if _HAS_CONTROL_HANDLER:
                try:
                    self._install_control_handlers(server, da_cache)
                except Exception as exc:
                    self._log.append("WARN", f"Control handler install skipped: {exc}")
            else:
                self._log.append(
                    "INFO",
                    "Control handler callbacks unavailable in this pyiec61850 build "
                    "— operate requests are still accepted via the REST /operate endpoint.",
                )

            iec61850.IedServer_start(server, config.port)

            if not iec61850.IedServer_isRunning(server):
                iec61850.IedServer_destroy(server)
                raise RuntimeError(
                    f"Failed to bind MMS server to port {config.port} on "
                    f"{config.interface}. Is another process using the port?"
                )

            # Initialize ctlModel on all DPC/SPC/INC controllable DOs so that
            # MMS clients see a non-zero control model and can call select/operate.
            # CDC_DPC_create does NOT auto-set ctlModel — we must write it.
            _init_control_models(server, da_cache, self._log)

            self._state.ied_server = server
            self._state.ied_model = model
            self._state.da_cache = da_cache
            self._state.start_time = datetime.now(timezone.utc)
            self._state.config = config

        self._poll_stop.clear()
        self._poll_thread = threading.Thread(
            target=self._connection_poll_loop, daemon=True, name="mms-conn-poll"
        )
        self._poll_thread.start()

        self._sim_thread = threading.Thread(
            target=self._value_simulation_loop, daemon=True, name="mms-val-sim"
        )
        self._sim_thread.start()

        self._log.append(
            "INFO",
            f"MMS server started — interface={config.interface} port={config.port} "
            f"auth={config.auth_mode} max_conn={config.max_connections}",
        )

    def stop(self) -> None:
        with self._state._lock:
            server = self._state.ied_server
            if server is None:
                return
            self._state.ied_server = None
            self._state.start_time = None

        self._poll_stop.set()

        iec61850.IedServer_stop(server)
        iec61850.IedServer_destroy(server)
        self._control_handlers.clear()
        self._log.append("INFO", "MMS server stopped")

    def get_status(self) -> dict:
        with self._state._lock:
            server = self._state.ied_server
            if server is None:
                return {
                    "running": False,
                    "connections": 0,
                    "uptime": None,
                    "port": self._state.config.port,
                    "interface": self._state.config.interface,
                    "scl_source": self._state.scl_source,
                    "da_count": 0,
                }
            conn_count = iec61850.IedServer_getNumberOfOpenConnections(server)
            return {
                "running": True,
                "connections": conn_count,
                "uptime": self._state.uptime_seconds,
                "port": self._state.config.port,
                "interface": self._state.config.interface,
                "scl_source": self._state.scl_source,
                "da_count": len(self._state.da_cache),
            }

    def read_value(self, ref: str) -> Optional[dict]:
        with self._state._lock:
            server = self._state.ied_server
            da = self._state.da_cache.get(ref)
        if server is None or da is None:
            return None
        try:
            mms_val = iec61850.IedServer_getAttributeValue(server, da)
            return _mms_value_to_dict(mms_val)
        except Exception:
            return None

    def write_value(self, ref: str, value: Any, value_type: Optional[str] = None) -> bool:
        with self._state._lock:
            server = self._state.ied_server
            da = self._state.da_cache.get(ref)
        if server is None or da is None:
            return False
        try:
            iec61850.IedServer_lockDataModel(server)
            try:
                _write_typed_value(server, da, value, value_type)
            finally:
                iec61850.IedServer_unlockDataModel(server)
            self._log.append("INFO", f"Write: {ref} = {value}")
            return True
        except Exception as exc:
            self._log.append("ERROR", f"Write failed: {ref}: {exc}")
            return False

    def get_device_tree(self) -> list[dict]:
        """
        Derive the device tree from da_cache keys. Each key is formatted as
        'LD/LN.DO.subattr' so we can extract (LD, LN) pairs without any C
        API walker (which segfaults on void* iteration in this SWIG wheel).
        """
        with self._state._lock:
            cache = self._state.da_cache
        if not cache:
            return []

        ld_to_lns: dict[str, set[str]] = {}
        for ref in cache:
            if "/" not in ref or "." not in ref:
                continue
            ld_part, rest = ref.split("/", 1)
            ln_part = rest.split(".", 1)[0]
            ld_to_lns.setdefault(ld_part, set()).add(ln_part)

        return [
            {"ld": ld, "logical_nodes": sorted(lns)}
            for ld, lns in sorted(ld_to_lns.items())
        ]

    def get_connections(self) -> list[dict]:
        with self._state._lock:
            server = self._state.ied_server
        if server is None:
            return []
        count = iec61850.IedServer_getNumberOfOpenConnections(server)
        return [{"id": i, "count": count} for i in range(count)]

    # ------------------------------------------------------------------
    # Background threads
    # ------------------------------------------------------------------

    def _connection_poll_loop(self) -> None:
        prev_count = -1
        while not self._poll_stop.wait(0.5):
            with self._state._lock:
                server = self._state.ied_server
                if server is None:
                    break
                count = iec61850.IedServer_getNumberOfOpenConnections(server)

            if count != prev_count:
                if prev_count >= 0:
                    direction = "connected" if count > prev_count else "disconnected"
                    self._log.append(
                        "INFO",
                        f"MMS client {direction} — active connections: {count}",
                    )
                self._state.broadcast({
                    "type": "server_status",
                    "data": {"running": True, "connections": count},
                })
                prev_count = count

    def _value_simulation_loop(self) -> None:
        t = 0.0
        while not self._poll_stop.wait(2.0):
            with self._state._lock:
                server = self._state.ied_server
                da_cache = dict(self._state.da_cache)

            if server is None:
                break

            try:
                iec61850.IedServer_lockDataModel(server)
                try:
                    _simulate_values(server, da_cache, t)
                finally:
                    iec61850.IedServer_unlockDataModel(server)
            except Exception as exc:
                self._log.append("WARN", f"Value simulation error: {exc}")

            t += 0.1

    def _install_control_handlers(self, server: Any, da_cache: dict) -> None:
        self._control_handlers = []
        # Find all controllable DOs by looking for refs ending in common control DAs
        do_refs_seen: set[str] = set()
        for ref in da_cache:
            # Control DOs end with $CO$Oper or $CO$SBO etc.
            if "$CO$" in ref:
                # Extract the DO reference (strip $CO$... suffix)
                parts = ref.split("$")
                if len(parts) >= 3:
                    do_ref = "$".join(parts[:-2])  # up to and including DO name
                    if do_ref not in do_refs_seen:
                        do_refs_seen.add(do_ref)
                        try:
                            node = iec61850.IedModel_getModelNodeByObjectReference(
                                self._state.ied_model,
                                do_ref.replace("$", "."),
                            )
                            if node:
                                handler = _ControlHandler(do_ref, self._log)
                                iec61850.IedServer_setControlHandler(
                                    server,
                                    iec61850.toDataObject(node),
                                    handler,
                                    None,
                                )
                                self._control_handlers.append(handler)
                        except Exception:
                            pass


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _mms_value_to_dict(mms_val: Any) -> Optional[dict]:
    if mms_val is None:
        return None
    try:
        t = iec61850.MmsValue_getType(mms_val)
        MMS_BOOLEAN   = iec61850.MMS_BOOLEAN
        MMS_INTEGER   = iec61850.MMS_INTEGER
        MMS_UNSIGNED  = iec61850.MMS_UNSIGNED
        MMS_FLOAT     = iec61850.MMS_FLOAT
        MMS_VISIBLE_STRING = iec61850.MMS_VISIBLE_STRING
        MMS_STRING    = iec61850.MMS_STRING
        MMS_UTC_TIME  = iec61850.MMS_UTC_TIME
        MMS_BIT_STRING = iec61850.MMS_BIT_STRING
        MMS_OCTET_STRING = iec61850.MMS_OCTET_STRING
        MMS_STRUCTURE = iec61850.MMS_STRUCTURE

        if t == MMS_BOOLEAN:
            return {"type": "BOOLEAN", "value": bool(iec61850.MmsValue_getBoolean(mms_val))}
        elif t == MMS_INTEGER:
            return {"type": "INT32", "value": iec61850.MmsValue_toInt32(mms_val)}
        elif t == MMS_UNSIGNED:
            return {"type": "UINT32", "value": iec61850.MmsValue_toUint32(mms_val)}
        elif t == MMS_FLOAT:
            return {"type": "FLOAT32", "value": round(iec61850.MmsValue_toFloat(mms_val), 6)}
        elif t in (MMS_VISIBLE_STRING, MMS_STRING):
            return {"type": "STRING", "value": iec61850.MmsValue_toString(mms_val)}
        elif t == MMS_UTC_TIME:
            ms = iec61850.MmsValue_getUtcTimeInMs(mms_val)
            return {"type": "TIMESTAMP", "value": ms}
        elif t == MMS_BIT_STRING:
            bits = iec61850.MmsValue_getBitStringAsInteger(mms_val)
            return {"type": "BITSTRING", "value": bits}
        elif t == MMS_STRUCTURE:
            return {"type": "STRUCTURE", "value": None}
        else:
            return {"type": "UNKNOWN", "value": None}
    except Exception:
        return {"type": "UNKNOWN", "value": None}


def _write_typed_value(server: Any, da: Any, value: Any, value_type: Optional[str]) -> None:
    mms_val = iec61850.IedServer_getAttributeValue(server, da)
    if mms_val is None:
        return
    t = iec61850.MmsValue_getType(mms_val)
    MMS_BOOLEAN  = iec61850.MMS_BOOLEAN
    MMS_INTEGER  = iec61850.MMS_INTEGER
    MMS_UNSIGNED = iec61850.MMS_UNSIGNED
    MMS_FLOAT    = iec61850.MMS_FLOAT
    MMS_VISIBLE_STRING = iec61850.MMS_VISIBLE_STRING
    MMS_STRING   = iec61850.MMS_STRING
    MMS_BIT_STRING = iec61850.MMS_BIT_STRING

    if t == MMS_BOOLEAN:
        iec61850.IedServer_updateBooleanAttributeValue(server, da, bool(value))
    elif t == MMS_INTEGER:
        iec61850.IedServer_updateInt32AttributeValue(server, da, int(value))
    elif t == MMS_UNSIGNED:
        iec61850.IedServer_updateUnsignedAttributeValue(server, da, int(value))
    elif t == MMS_FLOAT:
        iec61850.IedServer_updateFloatAttributeValue(server, da, float(value))
    elif t in (MMS_VISIBLE_STRING, MMS_STRING):
        iec61850.IedServer_updateVisibleStringAttributeValue(server, da, str(value))
    elif t == MMS_BIT_STRING:
        iec61850.IedServer_updateBitStringAttributeValue(server, da, int(value))


def _simulate_values(server: Any, da_cache: dict, t: float) -> None:
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    MMS_FLOAT    = iec61850.MMS_FLOAT
    MMS_UTC_TIME = iec61850.MMS_UTC_TIME
    MMS_INTEGER  = iec61850.MMS_INTEGER
    MMS_BOOLEAN  = iec61850.MMS_BOOLEAN

    for ref, da in da_cache.items():
        try:
            mms_val = iec61850.IedServer_getAttributeValue(server, da)
            if mms_val is None:
                continue
            val_type = iec61850.MmsValue_getType(mms_val)

            if val_type == MMS_FLOAT:
                # Determine simulation profile from reference
                base, amp = _get_profile(ref)
                phase = (hash(ref) % 1000) / 1000.0 * 2 * math.pi
                noise = (random.random() - 0.5) * amp * 0.05
                val = base + amp * math.sin(t + phase) + noise
                iec61850.IedServer_updateFloatAttributeValue(server, da, val)
            elif val_type == MMS_UTC_TIME:
                iec61850.IedServer_updateUTCTimeAttributeValue(server, da, now_ms)
        except Exception:
            continue


def _init_control_models(server: Any, da_cache: dict, log) -> None:
    """
    Write ctlModel = SBO_ENHANCED for DPC objects (XCBR.Pos, XSWI.Pos) so
    clients see ctlModel != 0 and can perform select/operate. libIEC61850's
    CDC_DPC_create does not initialize this attribute.
    """
    SBO_ENHANCED = 4   # CDC_CTL_MODEL_SBO_ENHANCED
    DIRECT_NORMAL = 1  # CDC_CTL_MODEL_DIRECT_NORMAL

    count = 0
    for ref, da in da_cache.items():
        if not ref.endswith(".ctlModel"):
            continue
        # Heuristic: DPC.Pos uses SBO enhanced; SPC/INC default to direct normal
        do_path = ref.rsplit(".", 1)[0]  # strip ".ctlModel"
        model_val = SBO_ENHANCED if ".Pos" in do_path else DIRECT_NORMAL
        try:
            iec61850.IedServer_lockDataModel(server)
            try:
                iec61850.IedServer_updateInt32AttributeValue(server, da, model_val)
            finally:
                iec61850.IedServer_unlockDataModel(server)
            count += 1
        except Exception:
            continue

    if count:
        log.append("INFO", f"Initialized ctlModel on {count} controllable DOs")


def _get_profile(ref: str) -> tuple[float, float]:
    for keyword, (base, amp) in _SIM_PROFILES.items():
        if keyword in ref:
            return base, amp
    return 0.0, 1.0


def _extract_device_tree(model: Any) -> list[dict]:
    """
    Build the device tree from the model.

    Uses IedModel_getLogicalDeviceCount + IedModel_getDeviceByIndex which
    DO accept an IedModel; the broken void* walker would require
    toModelNode(model), which the SWIG wheel rejects.
    """
    devices: list[dict] = []
    try:
        count = iec61850.IedModel_getLogicalDeviceCount(model)
    except Exception:
        return devices

    for i in range(count):
        try:
            ld = iec61850.IedModel_getDeviceByIndex(model, i)
            if ld is None:
                continue
            ld_node = iec61850.toModelNode(
                iec61850.LogicalDevice_getLogicalNode(ld, "LLN0")
            ) if iec61850.LogicalDevice_getLogicalNode(ld, "LLN0") else None
            ld_name = iec61850.ModelNode_getName(ld_node).split(".")[0] if ld_node else f"LD{i}"
        except Exception:
            continue

        # We don't have an "LN by index" call; the names we built are known.
        # Use known LN sets per LD-suffix.
        if ld_name.endswith("PROT"):
            lns = ["LLN0", "XCBR1", "XSWI1", "PDIS1", "PTOC1", "MMXU1"]
        elif ld_name.endswith("MEAS"):
            lns = ["LLN0", "MMXU1", "MMXU2", "MMXU3", "MSQI1", "MSTA1"]
        else:
            lns = ["LLN0"]
        # Filter to LNs that actually exist (defensive)
        lns = [n for n in lns if iec61850.LogicalDevice_getLogicalNode(ld, n)]
        devices.append({"ld": ld_name, "logical_nodes": lns})

    return devices
