from __future__ import annotations
from typing import Any, Optional

from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


class WriteValueRequest(BaseModel):
    value: Any
    value_type: Optional[str] = None


class OperateRequest(BaseModel):
    action: str = "operate"  # "operate" | "select"
    value: Optional[Any] = None
    test: bool = False


@router.get("/devices")
async def get_devices(request: Request):
    mms = request.app.state.mms_server
    return mms.get_device_tree()


@router.get("/datapoints")
async def get_datapoints(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    search: str = Query(""),
    ld: str = Query(""),
    ln: str = Query(""),
):
    app_st = request.app.state.app_state
    mms = request.app.state.mms_server

    with app_st._lock:
        refs = list(app_st.da_cache.keys())

    # Filter
    if search:
        low = search.lower()
        refs = [r for r in refs if low in r.lower()]
    if ld:
        refs = [r for r in refs if f"/{ld}" in r or r.startswith(ld)]
    if ln:
        refs = [r for r in refs if f"/{ln}$" in r or f"/{ln}." in r]

    total = len(refs)
    page_refs = refs[(page - 1) * page_size: page * page_size]

    items = []
    for ref in page_refs:
        val = mms.read_value(ref)
        items.append({"reference": ref, "value": val})

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
        "items": items,
    }


@router.get("/datapoints/{ref:path}")
async def get_datapoint(ref: str, request: Request):
    mms = request.app.state.mms_server
    val = mms.read_value(ref)
    if val is None:
        raise HTTPException(status_code=404, detail=f"Data attribute not found: {ref}")
    return {"reference": ref, "value": val}


@router.put("/datapoints/{ref:path}")
async def write_datapoint(ref: str, body: WriteValueRequest, request: Request):
    mms = request.app.state.mms_server
    if not mms.get_status()["running"]:
        raise HTTPException(status_code=503, detail="MMS server is not running")

    ok = mms.write_value(ref, body.value, body.value_type)
    if not ok:
        raise HTTPException(
            status_code=400,
            detail=f"Write failed for '{ref}'. Check that the reference is valid and the server is running.",
        )
    return {"success": True, "reference": ref, "value": body.value}


@router.post("/datapoints/{ref:path}/operate")
async def operate_datapoint(ref: str, body: OperateRequest, request: Request):
    log = request.app.state.log_buffer
    log.append("INFO", f"Control request: {ref} action={body.action} test={body.test}")
    # Direct operate: write value if provided
    if body.value is not None:
        mms = request.app.state.mms_server
        mms.write_value(ref, body.value)
    return {"success": True, "reference": ref, "action": body.action}
