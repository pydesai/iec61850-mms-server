from __future__ import annotations
import asyncio
from concurrent.futures import ThreadPoolExecutor

import psutil
from fastapi import APIRouter, Request, HTTPException

router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mms-api")


@router.get("/status")
async def get_status(request: Request):
    return request.app.state.mms_server.get_status()


@router.post("/start")
async def start_server(request: Request):
    app = request.app
    mms = app.state.mms_server
    app_st = app.state.app_state

    if app_st.is_running:
        raise HTTPException(status_code=409, detail="Server is already running")

    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(
            _executor,
            mms.start,
            app_st.ied_model,
            app_st.da_cache,
            app_st.config,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"success": True, "status": mms.get_status()}


@router.post("/stop")
async def stop_server(request: Request):
    app = request.app
    mms = app.state.mms_server

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_executor, mms.stop)
    return {"success": True}


@router.get("/interfaces")
async def get_interfaces():
    ifaces = []
    for name, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if hasattr(addr, "family"):
                family_name = addr.family.name if hasattr(addr.family, "name") else str(addr.family)
                if "AF_INET" in family_name:
                    ifaces.append({
                        "name": name,
                        "address": addr.address,
                        "family": family_name,
                        "netmask": addr.netmask,
                    })
    # Always include 0.0.0.0 as "all interfaces" option
    ifaces.insert(0, {
        "name": "all",
        "address": "0.0.0.0",
        "family": "AF_INET",
        "netmask": "0.0.0.0",
    })
    return ifaces
