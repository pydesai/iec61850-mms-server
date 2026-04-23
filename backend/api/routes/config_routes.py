from __future__ import annotations
import asyncio
import os
import shutil
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from typing import Optional, Literal

from config import ServerConfig

router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mms-cfg")
TLS_DIR = "/tmp/tls_certs"
os.makedirs(TLS_DIR, exist_ok=True)


class ConfigUpdateRequest(BaseModel):
    port: Optional[int] = Field(None, ge=1, le=65535)
    interface: Optional[str] = None
    auth_mode: Optional[Literal["none", "password", "tls"]] = None
    auth_username: Optional[str] = None
    auth_password: Optional[str] = None
    max_connections: Optional[int] = Field(None, ge=1, le=500)


@router.get("")
async def get_config(request: Request):
    cfg = request.app.state.app_state.config
    # Mask password in response
    d = cfg.model_dump()
    if d.get("auth_password"):
        d["auth_password"] = "***"
    return d


@router.put("")
async def update_config(body: ConfigUpdateRequest, request: Request):
    app = request.app
    app_st = app.state.app_state
    mms = app.state.mms_server

    with app_st._lock:
        cfg_dict = app_st.config.model_dump()
        update_data = {k: v for k, v in body.model_dump().items() if v is not None}
        cfg_dict.update(update_data)
        new_config = ServerConfig(**cfg_dict)
        app_st.config = new_config

    # Restart server with new config if currently running
    if app_st.is_running:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, mms.stop)
        await loop.run_in_executor(
            _executor,
            mms.start,
            app_st.ied_model,
            app_st.da_cache,
            new_config,
        )

    return {"success": True, "config": app_st.config.model_dump()}


@router.post("/tls/upload")
async def upload_tls_certs(
    cert: UploadFile = File(...),
    key: UploadFile = File(...),
    request: Request = None,
):
    app_st = request.app.state.app_state

    cert_path = os.path.join(TLS_DIR, "server.crt")
    key_path = os.path.join(TLS_DIR, "server.key")

    cert_bytes = await cert.read()
    key_bytes = await key.read()

    with open(cert_path, "wb") as f:
        f.write(cert_bytes)
    with open(key_path, "wb") as f:
        f.write(key_bytes)

    with app_st._lock:
        app_st.config.tls_cert_path = cert_path
        app_st.config.tls_key_path = key_path

    return {
        "success": True,
        "cert_path": cert_path,
        "key_path": key_path,
    }
