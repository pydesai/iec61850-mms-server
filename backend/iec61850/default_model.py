"""
Build the default 20-IED / 14,000+ data attribute model entirely via pyiec61850
dynamic model API. No SCL file is required for the default startup.

Model structure:
  20 IEDs (IED01..IED20)
    Each IED:
      {IED}PROT (LD): LLN0, XCBR1, XSWI1, PDIS1, PTOC1, MMXU1
      {IED}MEAS (LD): LLN0, MMXU1, MMXU2, MMXU3, MSQI1, MSTA1
"""
from __future__ import annotations
from typing import Any

import iec61850


# Functional constraint constants used in write policy setup
FC_SP = iec61850.IEC61850_FC_SP
FC_SV = iec61850.IEC61850_FC_SV
FC_CF = iec61850.IEC61850_FC_CF
FC_DC = iec61850.IEC61850_FC_DC

TRG_DATA_CHANGED = iec61850.TRG_OPT_DATA_CHANGED
TRG_INTEGRITY = iec61850.TRG_OPT_INTEGRITY
TRG_GI = iec61850.TRG_OPT_GI

RPT_SEQ = iec61850.RPT_OPT_SEQ_NUM
RPT_TS = iec61850.RPT_OPT_TIME_STAMP
RPT_REASON = iec61850.RPT_OPT_REASON_FOR_INCLUSION
RPT_DS_NAME = iec61850.RPT_OPT_DATA_SET_NAME
RPT_CONF_REV = iec61850.RPT_OPT_CONF_REV
RPT_ENTRY_ID = iec61850.RPT_OPT_ENTRY_ID

CTL_DIRECT = iec61850.CDC_CTL_MODEL_DIRECT_NORMAL
CTL_SBO = iec61850.CDC_CTL_MODEL_SBO_ENHANCED


def build_default_model() -> tuple[Any, dict[str, Any]]:
    """
    Returns (IedModel, da_cache) where da_cache maps object reference strings
    to DataAttribute node pointers for O(1) read/write access.
    """
    model = iec61850.IedModel_create("SIMULATOR")

    all_ld_refs: list[str] = []

    for ied_num in range(1, 21):
        ied_prefix = f"IED{ied_num:02d}"
        _build_prot_ld(model, ied_prefix, all_ld_refs)
        _build_meas_ld(model, ied_prefix, all_ld_refs)

    da_cache = _build_da_cache(model)
    return model, da_cache


def _build_prot_ld(model: Any, ied_prefix: str, ld_refs: list) -> None:
    ld_name = f"{ied_prefix}PROT"
    ld = iec61850.LogicalDevice_create(ld_name, model)

    lln0 = _build_lln0(ld)
    _build_xcbr1(ld)
    _build_xswi1(ld)
    _build_pdis1(ld)
    _build_ptoc1(ld)
    _build_mmxu(ld, "MMXU1")

    _add_rcbs_and_dataset(ld, lln0, "MMXU1")
    ld_refs.append(ld_name)


def _build_meas_ld(model: Any, ied_prefix: str, ld_refs: list) -> None:
    ld_name = f"{ied_prefix}MEAS"
    ld = iec61850.LogicalDevice_create(ld_name, model)

    lln0 = _build_lln0(ld)
    _build_mmxu(ld, "MMXU1")
    _build_mmxu(ld, "MMXU2")
    _build_mmxu(ld, "MMXU3")
    _build_msqi1(ld)
    _build_msta1(ld)

    _add_rcbs_and_dataset(ld, lln0, "MMXU1")
    ld_refs.append(ld_name)


def _build_lln0(parent_ld: Any) -> Any:
    ln = iec61850.LogicalNode_create("LLN0", parent_ld)
    node = iec61850.toModelNode(ln)
    iec61850.CDC_ENS_create("Mod",    node, 0)
    iec61850.CDC_ENS_create("Beh",    node, 0)
    iec61850.CDC_ENS_create("Health", node, 0)
    iec61850.CDC_LPL_create("NamPlt", node, 0)
    return ln


def _build_xcbr1(parent_ld: Any) -> Any:
    ln = iec61850.LogicalNode_create("XCBR1", parent_ld)
    node = iec61850.toModelNode(ln)
    iec61850.CDC_ENS_create("Mod",    node, 0)
    iec61850.CDC_ENS_create("Beh",    node, 0)
    iec61850.CDC_ENS_create("Health", node, 0)
    iec61850.CDC_LPL_create("NamPlt", node, 0)
    iec61850.CDC_INS_create("Loc",    node, 0)
    iec61850.CDC_INS_create("OpCnt",  node, 0)
    iec61850.CDC_DPC_create("Pos",    node, 0, CTL_SBO)
    iec61850.CDC_SPS_create("BlkOpn", node, 0)
    iec61850.CDC_SPS_create("BlkCls", node, 0)
    return ln


def _build_xswi1(parent_ld: Any) -> Any:
    ln = iec61850.LogicalNode_create("XSWI1", parent_ld)
    node = iec61850.toModelNode(ln)
    iec61850.CDC_ENS_create("Mod",    node, 0)
    iec61850.CDC_ENS_create("Beh",    node, 0)
    iec61850.CDC_ENS_create("Health", node, 0)
    iec61850.CDC_LPL_create("NamPlt", node, 0)
    iec61850.CDC_INS_create("Loc",    node, 0)
    iec61850.CDC_INS_create("OpCnt",  node, 0)
    iec61850.CDC_DPC_create("Pos",    node, 0, CTL_SBO)
    return ln


def _build_pdis1(parent_ld: Any) -> Any:
    ln = iec61850.LogicalNode_create("PDIS1", parent_ld)
    node = iec61850.toModelNode(ln)
    iec61850.CDC_ENS_create("Mod",    node, 0)
    iec61850.CDC_ENS_create("Beh",    node, 0)
    iec61850.CDC_ENS_create("Health", node, 0)
    iec61850.CDC_LPL_create("NamPlt", node, 0)
    iec61850.CDC_ACD_create("Op",     node, 0)
    iec61850.CDC_ACT_create("Str",    node, 0)
    iec61850.CDC_MV_create("Z",       node, 0, False)
    iec61850.CDC_MV_create("RStr",    node, 0, False)
    return ln


def _build_ptoc1(parent_ld: Any) -> Any:
    ln = iec61850.LogicalNode_create("PTOC1", parent_ld)
    node = iec61850.toModelNode(ln)
    iec61850.CDC_ENS_create("Mod",    node, 0)
    iec61850.CDC_ENS_create("Beh",    node, 0)
    iec61850.CDC_ENS_create("Health", node, 0)
    iec61850.CDC_LPL_create("NamPlt", node, 0)
    iec61850.CDC_ACD_create("Op",     node, 0)
    iec61850.CDC_ACT_create("Str",    node, 0)
    iec61850.CDC_MV_create("StrVal",  node, 0, False)
    iec61850.CDC_ING_create("StrMul", node, 0)
    iec61850.CDC_ING_create("StrVal2", node, 0)
    return ln


def _build_mmxu(parent_ld: Any, ln_name: str) -> Any:
    ln = iec61850.LogicalNode_create(ln_name, parent_ld)
    node = iec61850.toModelNode(ln)
    iec61850.CDC_ENS_create("Mod",    node, 0)
    iec61850.CDC_ENS_create("Beh",    node, 0)
    iec61850.CDC_ENS_create("Health", node, 0)
    iec61850.CDC_LPL_create("NamPlt", node, 0)

    # Scalar MV data objects
    for do_name in ["TotW", "TotVAr", "TotVA", "TotPF", "Hz"]:
        iec61850.CDC_MV_create(do_name, node, 0, False)

    # Three-phase WYE data objects
    for do_name in ["PhV", "A", "W", "VAr", "VA", "PF"]:
        iec61850.CDC_WYE_create(do_name, node, 0)

    return ln


def _build_msqi1(parent_ld: Any) -> Any:
    ln = iec61850.LogicalNode_create("MSQI1", parent_ld)
    node = iec61850.toModelNode(ln)
    iec61850.CDC_ENS_create("Mod",    node, 0)
    iec61850.CDC_ENS_create("Beh",    node, 0)
    iec61850.CDC_ENS_create("Health", node, 0)
    iec61850.CDC_LPL_create("NamPlt", node, 0)
    iec61850.CDC_WYE_create("SeqA",   node, 0)
    iec61850.CDC_WYE_create("SeqV",   node, 0)
    return ln


def _build_msta1(parent_ld: Any) -> Any:
    ln = iec61850.LogicalNode_create("MSTA1", parent_ld)
    node = iec61850.toModelNode(ln)
    iec61850.CDC_ENS_create("Mod",    node, 0)
    iec61850.CDC_ENS_create("Beh",    node, 0)
    iec61850.CDC_ENS_create("Health", node, 0)
    iec61850.CDC_LPL_create("NamPlt", node, 0)
    iec61850.CDC_MV_create("AvAmps",  node, 0, False)
    iec61850.CDC_MV_create("AvPPV",   node, 0, False)
    iec61850.CDC_MV_create("AvVolts", node, 0, False)
    iec61850.CDC_MV_create("AvWatts", node, 0, False)
    iec61850.CDC_INS_create("TotVAh",  node, 0)
    iec61850.CDC_INS_create("TotVArh", node, 0)
    iec61850.CDC_INS_create("TotWh",   node, 0)
    return ln


def _add_rcbs_and_dataset(parent_ld: Any, lln0: Any, mmxu_name: str) -> None:
    lln0_node = iec61850.toModelNode(lln0)

    ds = iec61850.DataSet_create("MeasDS", lln0_node)

    # Add FCDA entries referencing MMXU1 MX data
    mx_das = [
        f"{mmxu_name}$MX$TotW$mag$f",
        f"{mmxu_name}$MX$TotVAr$mag$f",
        f"{mmxu_name}$MX$TotVA$mag$f",
        f"{mmxu_name}$MX$TotPF$mag$f",
        f"{mmxu_name}$MX$Hz$mag$f",
        f"{mmxu_name}$MX$PhV$phsA$cVal$mag$f",
        f"{mmxu_name}$MX$PhV$phsB$cVal$mag$f",
        f"{mmxu_name}$MX$PhV$phsC$cVal$mag$f",
        f"{mmxu_name}$MX$A$phsA$cVal$mag$f",
        f"{mmxu_name}$MX$A$phsB$cVal$mag$f",
        f"{mmxu_name}$MX$A$phsC$cVal$mag$f",
    ]
    for da_ref in mx_das:
        iec61850.DataSetEntry_create(ds, da_ref, -1, None)

    # Buffered RCB
    iec61850.ReportControlBlock_create(
        "brcb01", lln0_node, "brcb01", True,
        "MeasDS", 1,
        TRG_DATA_CHANGED | TRG_INTEGRITY | TRG_GI,
        RPT_SEQ | RPT_TS | RPT_REASON | RPT_DS_NAME | RPT_CONF_REV | RPT_ENTRY_ID,
        50, 1000,
    )

    # Unbuffered RCB
    iec61850.ReportControlBlock_create(
        "urcb01", lln0_node, "urcb01", False,
        "MeasDS", 1,
        TRG_DATA_CHANGED | TRG_GI,
        RPT_SEQ | RPT_TS | RPT_REASON,
        50, 0,
    )


def _build_da_cache(model: Any) -> dict[str, Any]:
    """
    Walk the entire model and collect all DataAttribute references into a
    lookup cache. Best-effort: any failure traversing the C model tree
    returns whatever was collected so far rather than aborting startup.

    The MMS server itself does NOT depend on this cache; it's only used by
    the REST API for individual data-attribute read/write.
    """
    cache: dict[str, Any] = {}
    try:
        # Start from the IedModel root and walk each LogicalDevice
        first_ld = iec61850.IedModel_getFirstChild(model) if hasattr(
            iec61850, "IedModel_getFirstChild"
        ) else None

        if first_ld is None:
            # Fallback to enumerating LDs by index
            i = 0
            while True:
                ld = iec61850.IedModel_getDeviceByIndex(model, i) if hasattr(
                    iec61850, "IedModel_getDeviceByIndex"
                ) else None
                if ld is None:
                    break
                _walk_node_safe(iec61850.toModelNode(ld), cache)
                i += 1
        else:
            node = first_ld
            while node is not None:
                _walk_node_safe(node, cache)
                node = _safe_sibling(node)
    except Exception:
        # Final fallback: try walking from model as a ModelNode
        try:
            _walk_node_safe(iec61850.toModelNode(model), cache)
        except Exception:
            pass

    return cache


# ModelNodeType enum (from libiec61850 model.h):
#   LogicalDeviceModelType = 0
#   LogicalNodeModelType   = 1
#   DataObjectModelType    = 2
#   DataAttributeModelType = 3
_DATA_ATTRIBUTE_TYPE = 3


def _walk_node_safe(node: Any, cache: dict) -> None:
    if node is None:
        return
    try:
        node_type = iec61850.ModelNode_getType(node)
        if node_type == _DATA_ATTRIBUTE_TYPE:
            ref = iec61850.ModelNode_getObjectReference(node, None)
            if ref:
                cache[ref] = iec61850.toDataAttribute(node)
    except Exception:
        return

    # Walk children
    try:
        child = iec61850.ModelNode_getChild(node, None)
    except Exception:
        child = None

    while child is not None:
        _walk_node_safe(child, cache)
        child = _safe_sibling(child)


def _safe_sibling(node: Any) -> Any:
    try:
        return iec61850.ModelNode_getSibling(node)
    except Exception:
        return None
