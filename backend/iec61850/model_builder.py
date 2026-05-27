"""
Convert a ParsedSCL structure into a live pyiec61850 IedModel.
Returns (IedModel, da_cache) matching the format of default_model.py.
"""
from __future__ import annotations
from typing import Any

import pyiec61850 as iec61850
from iec61850.scl_parser import ParsedSCL, ParsedLN, ParsedDO, ParsedDOType

CTL_DIRECT = iec61850.CDC_CTL_MODEL_DIRECT_NORMAL
CTL_SBO = iec61850.CDC_CTL_MODEL_SBO_ENHANCED

# Map CDC string -> creator lambda(name, parent_node) -> DO node
CDC_CREATORS: dict[str, Any] = {
    "SPS":  lambda n, p: iec61850.CDC_SPS_create(n, p, 0),
    "DPS":  lambda n, p: iec61850.CDC_DPS_create(n, p, 0),
    "INS":  lambda n, p: iec61850.CDC_INS_create(n, p, 0),
    "ENS":  lambda n, p: iec61850.CDC_ENS_create(n, p, 0),
    "BCR":  lambda n, p: iec61850.CDC_BCR_create(n, p, 0),
    "MV":   lambda n, p: iec61850.CDC_MV_create(n, p, 0, False),
    "CMV":  lambda n, p: iec61850.CDC_CMV_create(n, p, 0),
    "SAV":  lambda n, p: iec61850.CDC_SAV_create(n, p, 0, False),
    "WYE":  lambda n, p: iec61850.CDC_WYE_create(n, p, 0),
    "DEL":  lambda n, p: iec61850.CDC_DEL_create(n, p, 0),
    "LPL":  lambda n, p: iec61850.CDC_LPL_create(n, p, 0),
    "DPL":  lambda n, p: iec61850.CDC_DPL_create(n, p, 0),
    "ACD":  lambda n, p: iec61850.CDC_ACD_create(n, p, 0),
    "ACT":  lambda n, p: iec61850.CDC_ACT_create(n, p, 0),
    "SPG":  lambda n, p: iec61850.CDC_SPG_create(n, p, 0),
    "ING":  lambda n, p: iec61850.CDC_ING_create(n, p, 0),
    "ASG":  lambda n, p: iec61850.CDC_ASG_create(n, p, 0, False),
    "SPC":  lambda n, p: iec61850.CDC_SPC_create(n, p, 0, CTL_DIRECT),
    "DPC":  lambda n, p: iec61850.CDC_DPC_create(n, p, 0, CTL_SBO),
    "INC":  lambda n, p: iec61850.CDC_INC_create(n, p, 0, CTL_DIRECT),
    "BSC":  lambda n, p: iec61850.CDC_BSC_create(n, p, 0, CTL_DIRECT, False),
    "ISC":  lambda n, p: iec61850.CDC_ISC_create(n, p, 0, CTL_DIRECT, False),
}

# Map SCL bType -> MMS type constant
BTYPE_TO_MMS: dict[str, Any] = {
    "BOOLEAN":     iec61850.MMS_BOOLEAN,
    "INT8":        iec61850.MMS_INTEGER,
    "INT16":       iec61850.MMS_INTEGER,
    "INT32":       iec61850.MMS_INTEGER,
    "INT64":       iec61850.MMS_INTEGER,
    "INT8U":       iec61850.MMS_UNSIGNED,
    "INT16U":      iec61850.MMS_UNSIGNED,
    "INT24U":      iec61850.MMS_UNSIGNED,
    "INT32U":      iec61850.MMS_UNSIGNED,
    "FLOAT32":     iec61850.MMS_FLOAT,
    "FLOAT64":     iec61850.MMS_FLOAT,
    "Enum":        iec61850.MMS_INTEGER,
    "Dbpos":       iec61850.MMS_BIT_STRING,
    "Tcmd":        iec61850.MMS_BIT_STRING,
    "Quality":     iec61850.MMS_BIT_STRING,
    "Timestamp":   iec61850.MMS_UTC_TIME,
    "VisString32": iec61850.MMS_VISIBLE_STRING,
    "VisString64": iec61850.MMS_VISIBLE_STRING,
    "VisString65": iec61850.MMS_VISIBLE_STRING,
    "VisString129": iec61850.MMS_VISIBLE_STRING,
    "VisString255": iec61850.MMS_VISIBLE_STRING,
    "Unicode255":  iec61850.MMS_STRING,
    "OctetString6": iec61850.MMS_OCTET_STRING,
    "OctetString64": iec61850.MMS_OCTET_STRING,
}

FC_MAP: dict[str, Any] = {
    "ST": iec61850.IEC61850_FC_ST,
    "MX": iec61850.IEC61850_FC_MX,
    "SP": iec61850.IEC61850_FC_SP,
    "SV": iec61850.IEC61850_FC_SV,
    "CF": iec61850.IEC61850_FC_CF,
    "DC": iec61850.IEC61850_FC_DC,
    "SG": iec61850.IEC61850_FC_SG,
    "SE": iec61850.IEC61850_FC_SE,
    "SR": iec61850.IEC61850_FC_SR,
    "OR": iec61850.IEC61850_FC_OR,
    "BL": iec61850.IEC61850_FC_BL,
    "CO": iec61850.IEC61850_FC_CO,
    "EX": iec61850.IEC61850_FC_EX,
}


def build_model_from_scl(parsed: ParsedSCL) -> tuple[Any, dict[str, Any]]:
    # Use empty IedModel name; SCL IED name is baked into LD inst via build_ld below
    model = iec61850.IedModel_create("")

    expected_refs: list[str] = []

    for ied in parsed.ieds:
        for ld in ied.logical_devices:
            ld_key = f"{ied.name}{ld.inst}"
            ld_obj = iec61850.LogicalDevice_create(ld_key, model)
            for ln in ld.logical_nodes:
                ln_refs = _build_ln(ln, ld_obj, parsed.do_types, ld_key)
                expected_refs.extend(ln_refs)

    # Stash expected refs so _build_da_cache can resolve them
    _PENDING_DA_REFS[id(model)] = expected_refs
    da_cache = _build_da_cache(model)
    return model, da_cache


def _build_ln(
    ln: ParsedLN,
    parent_ld: Any,
    do_types: dict[str, ParsedDOType],
    ld_key: str,
) -> list[str]:
    ln_name = (ln.prefix or "") + ln.ln_class + (ln.inst or "")
    if ln.ln_class == "LLN0":
        ln_name = "LLN0"

    ln_obj = iec61850.LogicalNode_create(ln_name, parent_ld)
    ln_node = iec61850.toModelNode(ln_obj)

    refs: list[str] = []
    for do in ln.data_objects:
        do_type = do_types.get(do.type_ref)
        if do_type is None:
            continue
        creator = CDC_CREATORS.get(do_type.cdc)
        if creator:
            creator(do.name, ln_node)
            # Generate expected sub-attribute refs for this CDC
            do_ref = f"{ld_key}/{ln_name}.{do.name}"
            for sub in CDC_SUB_ATTRS.get(do_type.cdc, []):
                refs.append(f"{do_ref}.{sub}")
        else:
            _build_custom_do(do.name, do_type, ln_node, do_types)
    return refs


def _build_custom_do(
    do_name: str,
    do_type: ParsedDOType,
    parent_ln_node: Any,
    do_types: dict[str, ParsedDOType],
) -> None:
    do_obj = iec61850.DataObject_create(do_name, parent_ln_node, 0)
    do_node = iec61850.toModelNode(do_obj)
    for da in do_type.das:
        _build_da(da, do_node, do_types)


def _build_da(da: Any, parent_node: Any, do_types: dict[str, ParsedDOType]) -> None:
    if da.btype == "Struct":
        sub_da_obj = iec61850.DataAttribute_create(
            da.name, parent_node, iec61850.MMS_STRUCTURE,
            FC_MAP.get(da.fc, iec61850.IEC61850_FC_MX), 0, 0,
        )
        sub_node = iec61850.toModelNode(sub_da_obj)
        # Recursively build sub-DAs from DAType reference (simplified)
        return

    mms_type = BTYPE_TO_MMS.get(da.btype, iec61850.MMS_VISIBLE_STRING)
    fc = FC_MAP.get(da.fc, iec61850.IEC61850_FC_MX)
    iec61850.DataAttribute_create(da.name, parent_node, mms_type, fc, 0, 0)


# CDC sub-attribute templates (shared with default_model)
from iec61850.default_model import CDC_SUB_ATTRS

_DATA_ATTRIBUTE_TYPE = 3


def _build_da_cache(model: Any) -> dict[str, Any]:
    """
    Use the parsed SCL structure (passed alongside the model) to enumerate
    every DO ref and resolve its sub-attributes via getModelNodeByObjectReference.
    This is robust against SWIG walker bugs.

    For the simplified SCL builder we attach the parsed reference list to the
    model via a module-level dict; see build_model_from_scl below.
    """
    cache: dict[str, Any] = {}
    refs = _PENDING_DA_REFS.pop(id(model), [])
    for full_ref in refs:
        try:
            node = iec61850.IedModel_getModelNodeByShortObjectReference(model, full_ref)
            if node is None:
                continue
            try:
                if iec61850.ModelNode_getType(node) != _DATA_ATTRIBUTE_TYPE:
                    continue
            except Exception:
                pass
            cache[full_ref] = iec61850.toDataAttribute(node)
        except Exception:
            continue
    return cache


# Module-level map: model_id -> list[ref_strings]
# Populated by build_model_from_scl, consumed by _build_da_cache
_PENDING_DA_REFS: dict[int, list[str]] = {}
