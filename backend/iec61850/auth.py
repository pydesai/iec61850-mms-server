"""
MMS/ACSE password authentication via ctypes.

libIEC61850's AcseAuthenticator is not exposed through pyiec61850's SWIG
interface as a director class, so we use ctypes to create a real C function
pointer and call IedServer_setAuthenticator() directly against the bundled .so.
"""
from __future__ import annotations
import ctypes
import ctypes.util
import os
import glob
from typing import Optional

# Module-level ref to prevent garbage collection of the callback
_callback_ref: Optional[ctypes.CFUNCTYPE] = None
_lib: Optional[ctypes.CDLL] = None


def _get_lib() -> ctypes.CDLL:
    global _lib
    if _lib is not None:
        return _lib

    import iec61850 as _iec61850_mod
    mod_dir = os.path.dirname(_iec61850_mod.__file__)

    # Find the compiled .so — name varies by Python version and arch
    patterns = [
        os.path.join(mod_dir, "_iec61850*.so"),
        os.path.join(mod_dir, "_iec61850*.pyd"),
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            _lib = ctypes.CDLL(matches[0])
            return _lib

    # Fallback: try loading by name via ctypes.util
    lib_path = ctypes.util.find_library("iec61850")
    if lib_path:
        _lib = ctypes.CDLL(lib_path)
        return _lib

    raise RuntimeError("Could not locate libiec61850 shared library for ctypes binding")


# AcseAuthenticationParameter struct layout from libIEC61850 iso_connection_parameters.h:
# typedef enum { ACSE_AUTH_NONE = 0, ACSE_AUTH_PASSWORD = 1, ACSE_AUTH_CERTIFICATE = 2 } AcseAuthenticationMechanism;
# struct AcseAuthenticationParameter_s {
#   AcseAuthenticationMechanism mechanism;  // int (4 bytes)
#   union {
#     struct { uint8_t* octetString; int passwordLength; };
#     struct { ... certificate stuff ... };
#   };
# };
ACSE_AUTH_PASSWORD = 1


class _AcseAuthParam(ctypes.Structure):
    _fields_ = [
        ("mechanism", ctypes.c_int),
        ("octet_string", ctypes.c_void_p),
        ("password_length", ctypes.c_int),
    ]


_AUTHENTICATOR_FTYPE = ctypes.CFUNCTYPE(
    ctypes.c_bool,
    ctypes.c_void_p,   # parameter (user data)
    ctypes.c_void_p,   # authParameter
    ctypes.POINTER(ctypes.c_void_p),  # securityToken
    ctypes.c_void_p,   # appReference
)


def install_password_authenticator(ied_server_swig_obj: object, password: str) -> None:
    global _callback_ref

    lib = _get_lib()
    pwd_bytes = password.encode("utf-8")

    def _authenticator(parameter, auth_param_ptr, security_token, app_ref):
        try:
            if not auth_param_ptr:
                return False
            param = _AcseAuthParam.from_address(auth_param_ptr)
            if param.mechanism != ACSE_AUTH_PASSWORD:
                return False
            if not param.octet_string or param.password_length <= 0:
                return False
            client_pwd = ctypes.string_at(param.octet_string, param.password_length)
            return client_pwd == pwd_bytes
        except Exception:
            return False

    _callback_ref = _AUTHENTICATOR_FTYPE(_authenticator)

    # Extract raw pointer from the SWIG IedServer opaque object.
    # pyiec61850 wraps C pointers in SWIG proxy objects; the integer value
    # of the proxy object is the C pointer address.
    try:
        server_addr = int(ied_server_swig_obj)
    except (TypeError, ValueError):
        # Alternative extraction method via string repr "0x..."
        s = str(ied_server_swig_obj)
        if "0x" in s:
            server_addr = int(s.split("0x")[1].split(">")[0], 16)
        else:
            raise RuntimeError(f"Cannot extract C pointer from SWIG object: {s}")

    lib.IedServer_setAuthenticator.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    lib.IedServer_setAuthenticator.restype = None
    lib.IedServer_setAuthenticator(server_addr, _callback_ref, None)
