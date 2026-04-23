from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import ServerConfig
from state.app_state import AppState
from state.log_buffer import LogBuffer
from iec61850.server import MmsServer
from iec61850.default_model import build_default_model
from api.routes import (
    server_routes,
    scl_routes,
    datapoints_routes,
    connections_routes,
    logs_routes,
    config_routes,
)
from api.websocket import websocket_endpoint, ws_manager

_startup_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mms-startup")

# Shared singletons
app_state = AppState()
log_buffer = LogBuffer(maxlen=10_000)
mms_server = MmsServer(app_state, log_buffer)


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()

    app_state.event_loop = loop
    log_buffer.set_event_loop(loop)
    app_state._ws_broadcaster = ws_manager.broadcast

    log_buffer.append("INFO", "Building default IEC 61850 model (20 IEDs, 14,000+ data attributes)...")

    # Build model in thread pool (CPU-bound C calls)
    model, da_cache = await loop.run_in_executor(_startup_executor, build_default_model)

    with app_state._lock:
        app_state.ied_model = model
        app_state.da_cache = da_cache
        app_state.scl_source = "default"

    log_buffer.append("INFO", f"Default model built — {len(da_cache)} data attributes indexed")

    # Start MMS server
    try:
        await loop.run_in_executor(
            _startup_executor,
            mms_server.start,
            model,
            da_cache,
            app_state.config,
        )
    except RuntimeError as exc:
        log_buffer.append(
            "WARN",
            f"MMS server could not start on port {app_state.config.port}: {exc}. "
            "Change the port in Settings and click Start.",
        )

    yield

    # Graceful shutdown
    log_buffer.append("INFO", "Shutting down MMS server...")
    mms_server.stop()


app = FastAPI(
    title="IEC 61850 MMS Simulator",
    description="IEC 61850 MMS protocol server simulator with enterprise UI",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inject shared singletons into app.state for route access
app.state.mms_server = mms_server
app.state.app_state = app_state
app.state.log_buffer = log_buffer

# Routers
app.include_router(server_routes.router,      prefix="/api/server",  tags=["server"])
app.include_router(scl_routes.router,         prefix="/api/scl",     tags=["scl"])
app.include_router(datapoints_routes.router,  prefix="/api",         tags=["datapoints"])
app.include_router(connections_routes.router, prefix="/api",         tags=["connections"])
app.include_router(logs_routes.router,        prefix="/api",         tags=["logs"])
app.include_router(config_routes.router,      prefix="/api/config",  tags=["config"])

app.add_api_websocket_route("/ws", websocket_endpoint)


@app.get("/health")
async def health():
    return {"status": "ok"}
