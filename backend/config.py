from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    port: int = Field(default=102, ge=1, le=65535)
    interface: str = "0.0.0.0"
    auth_mode: Literal["none", "password", "tls"] = "none"
    auth_username: Optional[str] = None
    auth_password: Optional[str] = None
    tls_cert_path: Optional[str] = None
    tls_key_path: Optional[str] = None
    max_connections: int = Field(default=50, ge=1, le=500)
    report_buffer_size: int = Field(default=65536, ge=4096)
