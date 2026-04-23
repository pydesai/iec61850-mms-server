from __future__ import annotations
import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, UploadFile, File

from iec61850.scl_parser import parse_scl
from iec61850.model_builder import build_model_from_scl

router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mms-scl")
UPLOAD_DIR = "/tmp/scl_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".icd", ".cid", ".scd", ".iid"}


@router.post("/upload")
async def upload_scl(file: UploadFile = File(...), request: Request = None):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # Validate by parsing
    try:
        parsed = parse_scl(content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"SCL parse error: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid SCL file: {exc}")

    # Save to disk
    filename = file.filename or "unknown.icd"
    dest = os.path.join(UPLOAD_DIR, filename)
    with open(dest, "wb") as f:
        f.write(content)

    return {
        "filename": filename,
        "size_bytes": len(content),
        "ied_count": len(parsed.ieds),
        "device_count": sum(len(ied.logical_devices) for ied in parsed.ieds),
        "ln_count": sum(
            len(ld.logical_nodes)
            for ied in parsed.ieds
            for ld in ied.logical_devices
        ),
    }


@router.get("/files")
async def list_scl_files():
    files = []
    for fname in sorted(os.listdir(UPLOAD_DIR)):
        fpath = os.path.join(UPLOAD_DIR, fname)
        if os.path.isfile(fpath):
            stat = os.stat(fpath)
            files.append({
                "filename": fname,
                "size_bytes": stat.st_size,
                "modified": stat.st_mtime,
            })
    return files


@router.post("/load/{filename}")
async def load_scl(filename: str, request: Request):
    path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"SCL file '{filename}' not found")

    app = request.app
    app_st = app.state.app_state
    mms = app.state.mms_server
    log = app.state.log_buffer

    with open(path, "rb") as f:
        content = f.read()

    try:
        parsed = parse_scl(content)
        model, da_cache = build_model_from_scl(parsed)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to build model: {exc}")

    loop = asyncio.get_event_loop()
    was_running = app_st.is_running

    if was_running:
        await loop.run_in_executor(_executor, mms.stop)

    with app_st._lock:
        app_st.ied_model = model
        app_st.da_cache = da_cache
        app_st.scl_source = filename

    if was_running:
        try:
            await loop.run_in_executor(
                _executor,
                mms.start,
                model,
                da_cache,
                app_st.config,
            )
        except RuntimeError as exc:
            log.append("ERROR", f"Failed to restart after SCL load: {exc}")
            raise HTTPException(status_code=500, detail=str(exc))

    log.append("INFO", f"SCL loaded: {filename} — {len(da_cache)} data attributes")
    return {
        "success": True,
        "filename": filename,
        "da_count": len(da_cache),
        "ied_count": len(parsed.ieds),
    }


@router.delete("/{filename}")
async def delete_scl(filename: str):
    path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    os.remove(path)
    return {"success": True}
