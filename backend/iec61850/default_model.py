"""
Build the default 20-IED IEC 61850 model entirely via pyiec61850 dynamic API.

Strategy:
1. Build the model with explicit CDC_*_create calls.
2. Track every (LD, LN, DO, CDC) tuple as we build.
3. After the full model is constructed, enumerate each CDC's well-known
   sub-attribute paths and resolve them via IedModel_getModelNodeByObjectReference,
   populating the da_cache as ref-string -> DataAttribute pointer.

This avoids the broken `void*` LinkedList iteration in the PyPI SWIG wheel
and is more deterministic than a tree walker.
"""
from __future__ import annotations
from typing import Any

import pyiec61850 as iec61850


# ---------------------------------------------------------------
# Standard FC + report option masks
# ---------------------------------------------------------------
TRG_DATA_CHANGED = iec61850.TRG_OPT_DATA_CHANGED
TRG_INTEGRITY    = iec61850.TRG_OPT_INTEGRITY
TRG_GI           = iec61850.TRG_OPT_GI
TRG_QCHG         = iec61850.TRG_OPT_QUALITY_CHANGED

RPT_SEQ       = iec61850.RPT_OPT_SEQ_NUM
RPT_TS        = iec61850.RPT_OPT_TIME_STAMP
RPT_REASON    = iec61850.RPT_OPT_REASON_FOR_INCLUSION
RPT_DS        = iec61850.RPT_OPT_DATA_SET
RPT_CONF_REV  = iec61850.RPT_OPT_CONF_REV
RPT_ENTRY_ID  = iec61850.RPT_OPT_ENTRY_ID
RPT_DATA_REF  = iec61850.RPT_OPT_DATA_REFERENCE

CTL_DIRECT = iec61850.CDC_CTL_MODEL_DIRECT_NORMAL
CTL_SBO    = iec61850.CDC_CTL_MODEL_SBO_ENHANCED


# ---------------------------------------------------------------
# CDC-specific sub-attribute templates
# Each CDC defines which DA paths exist underneath a DO of that type.
# Format: (path_after_DO, fc_for_log) — only path matters for lookup.
# ---------------------------------------------------------------
CDC_SUB_ATTRS: dict[str, list[str]] = {
    "ENS": ["stVal", "q", "t"],
    "SPS": ["stVal", "q", "t"],
    "DPS": ["stVal", "q", "t"],
    "INS": ["stVal", "q", "t"],
    "ENG": ["setVal"],
    "ING": ["setVal"],
    "ASG": ["setMag.f"],
    "SPG": ["setVal"],
    "MV":  ["mag.f", "q", "t"],
    "CMV": ["cVal.mag.f", "cVal.ang.f", "q", "t"],
    "SAV": ["instMag.f", "q", "t"],
    "WYE": [
        "phsA.cVal.mag.f", "phsA.cVal.ang.f", "phsA.q", "phsA.t",
        "phsB.cVal.mag.f", "phsB.cVal.ang.f", "phsB.q", "phsB.t",
        "phsC.cVal.mag.f", "phsC.cVal.ang.f", "phsC.q", "phsC.t",
    ],
    "DEL": [
        "phsAB.cVal.mag.f", "phsAB.cVal.ang.f",
        "phsBC.cVal.mag.f", "phsBC.cVal.ang.f",
        "phsCA.cVal.mag.f", "phsCA.cVal.ang.f",
    ],
    "LPL": ["vendor", "swRev", "d"],
    "DPL": ["vendor", "hwRev", "swRev", "serNum", "model", "location"],
    "BCR": ["actVal", "q", "t"],
    "ACD": ["general", "phsA", "phsB", "phsC", "neut", "q", "t"],
    "ACT": ["general", "phsA", "phsB", "phsC", "neut", "q", "t"],
    "DPC": ["stVal", "q", "t", "ctlModel"],
    "SPC": ["stVal", "q", "t", "ctlModel"],
    "INC": ["stVal", "q", "t", "ctlModel"],
}


# ---------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------
def build_default_model() -> tuple[Any, dict[str, Any]]:
    """
    Returns (IedModel, da_cache).

    The model has 20 IEDs × (LD_PROT + LD_MEAS), each with multiple LNs
    covering common IEC 61850 logical-node classes (XCBR, XSWI, PDIS,
    PTOC, MMXU, MSQI, MSTA). The da_cache maps full object references
    to DataAttribute pointers for fast read/write.
    """
    # Empty IedModel name keeps object refs clean (IED01PROT/... not SIMULATORIED01PROT/...)
    model = iec61850.IedModel_create("")
    do_refs: list[tuple[str, str]] = []  # (ref, cdc)

    for ied_num in range(1, 21):
        ied_prefix = f"IED{ied_num:02d}"
        do_refs.extend(_build_prot_ld(model, ied_prefix))
        do_refs.extend(_build_meas_ld(model, ied_prefix))

    da_cache = _resolve_attributes(model, do_refs)
    return model, da_cache


# ---------------------------------------------------------------
# Logical Device builders
# ---------------------------------------------------------------
def _build_prot_ld(model: Any, ied_prefix: str) -> list[tuple[str, str]]:
    ld_name = f"{ied_prefix}PROT"
    ld = iec61850.LogicalDevice_create(ld_name, model)
    refs: list[tuple[str, str]] = []

    refs.extend(_build_lln0(ld, ld_name))
    refs.extend(_build_xcbr1(ld, ld_name))
    refs.extend(_build_xswi1(ld, ld_name))
    refs.extend(_build_pdis1(ld, ld_name))
    refs.extend(_build_ptoc1(ld, ld_name))
    refs.extend(_build_mmxu(ld, ld_name, "MMXU1"))

    _add_rcbs(ld, "MMXU1")
    return refs


def _build_meas_ld(model: Any, ied_prefix: str) -> list[tuple[str, str]]:
    ld_name = f"{ied_prefix}MEAS"
    ld = iec61850.LogicalDevice_create(ld_name, model)
    refs: list[tuple[str, str]] = []

    refs.extend(_build_lln0(ld, ld_name))
    refs.extend(_build_mmxu(ld, ld_name, "MMXU1"))
    refs.extend(_build_mmxu(ld, ld_name, "MMXU2"))
    refs.extend(_build_mmxu(ld, ld_name, "MMXU3"))
    refs.extend(_build_msqi1(ld, ld_name))
    refs.extend(_build_msta1(ld, ld_name))

    _add_rcbs(ld, "MMXU1")
    return refs


# ---------------------------------------------------------------
# Logical Node builders
# Each returns a list of (DO_ref_string, CDC_string) tuples.
# ---------------------------------------------------------------
def _build_lln0(ld: Any, ld_name: str) -> list[tuple[str, str]]:
    ln = iec61850.LogicalNode_create("LLN0", ld)
    node = iec61850.toModelNode(ln)
    iec61850.CDC_ENS_create("Mod",    node, 0)
    iec61850.CDC_ENS_create("Beh",    node, 0)
    iec61850.CDC_ENS_create("Health", node, 0)
    iec61850.CDC_LPL_create("NamPlt", node, 0)
    base = f"{ld_name}/LLN0"
    return [
        (f"{base}.Mod", "ENS"),
        (f"{base}.Beh", "ENS"),
        (f"{base}.Health", "ENS"),
        (f"{base}.NamPlt", "LPL"),
    ]


def _build_xcbr1(ld: Any, ld_name: str) -> list[tuple[str, str]]:
    ln = iec61850.LogicalNode_create("XCBR1", ld)
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
    base = f"{ld_name}/XCBR1"
    return [
        (f"{base}.Mod", "ENS"), (f"{base}.Beh", "ENS"),
        (f"{base}.Health", "ENS"), (f"{base}.NamPlt", "LPL"),
        (f"{base}.Loc", "INS"), (f"{base}.OpCnt", "INS"),
        (f"{base}.Pos", "DPC"),
        (f"{base}.BlkOpn", "SPS"), (f"{base}.BlkCls", "SPS"),
    ]


def _build_xswi1(ld: Any, ld_name: str) -> list[tuple[str, str]]:
    ln = iec61850.LogicalNode_create("XSWI1", ld)
    node = iec61850.toModelNode(ln)
    iec61850.CDC_ENS_create("Mod",    node, 0)
    iec61850.CDC_ENS_create("Beh",    node, 0)
    iec61850.CDC_ENS_create("Health", node, 0)
    iec61850.CDC_LPL_create("NamPlt", node, 0)
    iec61850.CDC_INS_create("Loc",    node, 0)
    iec61850.CDC_INS_create("OpCnt",  node, 0)
    iec61850.CDC_DPC_create("Pos",    node, 0, CTL_SBO)
    base = f"{ld_name}/XSWI1"
    return [
        (f"{base}.Mod", "ENS"), (f"{base}.Beh", "ENS"),
        (f"{base}.Health", "ENS"), (f"{base}.NamPlt", "LPL"),
        (f"{base}.Loc", "INS"), (f"{base}.OpCnt", "INS"),
        (f"{base}.Pos", "DPC"),
    ]


def _build_pdis1(ld: Any, ld_name: str) -> list[tuple[str, str]]:
    ln = iec61850.LogicalNode_create("PDIS1", ld)
    node = iec61850.toModelNode(ln)
    iec61850.CDC_ENS_create("Mod",    node, 0)
    iec61850.CDC_ENS_create("Beh",    node, 0)
    iec61850.CDC_ENS_create("Health", node, 0)
    iec61850.CDC_LPL_create("NamPlt", node, 0)
    iec61850.CDC_ACD_create("Op",     node, 0)
    iec61850.CDC_ACT_create("Str",    node, 0)
    iec61850.CDC_MV_create("Z",       node, 0, False)
    iec61850.CDC_MV_create("RStr",    node, 0, False)
    base = f"{ld_name}/PDIS1"
    return [
        (f"{base}.Mod", "ENS"), (f"{base}.Beh", "ENS"),
        (f"{base}.Health", "ENS"), (f"{base}.NamPlt", "LPL"),
        (f"{base}.Op", "ACD"), (f"{base}.Str", "ACT"),
        (f"{base}.Z", "MV"), (f"{base}.RStr", "MV"),
    ]


def _build_ptoc1(ld: Any, ld_name: str) -> list[tuple[str, str]]:
    ln = iec61850.LogicalNode_create("PTOC1", ld)
    node = iec61850.toModelNode(ln)
    iec61850.CDC_ENS_create("Mod",    node, 0)
    iec61850.CDC_ENS_create("Beh",    node, 0)
    iec61850.CDC_ENS_create("Health", node, 0)
    iec61850.CDC_LPL_create("NamPlt", node, 0)
    iec61850.CDC_ACD_create("Op",     node, 0)
    iec61850.CDC_ACT_create("Str",    node, 0)
    iec61850.CDC_MV_create("StrVal",  node, 0, False)
    iec61850.CDC_ING_create("StrMul", node, 0)
    base = f"{ld_name}/PTOC1"
    return [
        (f"{base}.Mod", "ENS"), (f"{base}.Beh", "ENS"),
        (f"{base}.Health", "ENS"), (f"{base}.NamPlt", "LPL"),
        (f"{base}.Op", "ACD"), (f"{base}.Str", "ACT"),
        (f"{base}.StrVal", "MV"), (f"{base}.StrMul", "ING"),
    ]


def _build_mmxu(ld: Any, ld_name: str, ln_name: str) -> list[tuple[str, str]]:
    ln = iec61850.LogicalNode_create(ln_name, ld)
    node = iec61850.toModelNode(ln)
    iec61850.CDC_ENS_create("Mod",    node, 0)
    iec61850.CDC_ENS_create("Beh",    node, 0)
    iec61850.CDC_ENS_create("Health", node, 0)
    iec61850.CDC_LPL_create("NamPlt", node, 0)
    for do_name in ["TotW", "TotVAr", "TotVA", "TotPF", "Hz"]:
        iec61850.CDC_MV_create(do_name, node, 0, False)
    for do_name in ["PhV", "A", "W", "VAr", "VA", "PF"]:
        iec61850.CDC_WYE_create(do_name, node, 0)
    base = f"{ld_name}/{ln_name}"
    refs = [
        (f"{base}.Mod", "ENS"), (f"{base}.Beh", "ENS"),
        (f"{base}.Health", "ENS"), (f"{base}.NamPlt", "LPL"),
    ]
    for do_name in ["TotW", "TotVAr", "TotVA", "TotPF", "Hz"]:
        refs.append((f"{base}.{do_name}", "MV"))
    for do_name in ["PhV", "A", "W", "VAr", "VA", "PF"]:
        refs.append((f"{base}.{do_name}", "WYE"))
    return refs


def _build_msqi1(ld: Any, ld_name: str) -> list[tuple[str, str]]:
    ln = iec61850.LogicalNode_create("MSQI1", ld)
    node = iec61850.toModelNode(ln)
    iec61850.CDC_ENS_create("Mod",    node, 0)
    iec61850.CDC_ENS_create("Beh",    node, 0)
    iec61850.CDC_ENS_create("Health", node, 0)
    iec61850.CDC_LPL_create("NamPlt", node, 0)
    iec61850.CDC_WYE_create("SeqA",   node, 0)
    iec61850.CDC_WYE_create("SeqV",   node, 0)
    base = f"{ld_name}/MSQI1"
    return [
        (f"{base}.Mod", "ENS"), (f"{base}.Beh", "ENS"),
        (f"{base}.Health", "ENS"), (f"{base}.NamPlt", "LPL"),
        (f"{base}.SeqA", "WYE"), (f"{base}.SeqV", "WYE"),
    ]


def _build_msta1(ld: Any, ld_name: str) -> list[tuple[str, str]]:
    ln = iec61850.LogicalNode_create("MSTA1", ld)
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
    base = f"{ld_name}/MSTA1"
    return [
        (f"{base}.Mod", "ENS"), (f"{base}.Beh", "ENS"),
        (f"{base}.Health", "ENS"), (f"{base}.NamPlt", "LPL"),
        (f"{base}.AvAmps", "MV"), (f"{base}.AvPPV", "MV"),
        (f"{base}.AvVolts", "MV"), (f"{base}.AvWatts", "MV"),
        (f"{base}.TotVAh", "INS"), (f"{base}.TotVArh", "INS"),
        (f"{base}.TotWh", "INS"),
    ]


# ---------------------------------------------------------------
# Report Control Blocks + Datasets
# ---------------------------------------------------------------
def _add_rcbs(ld: Any, mmxu_name: str) -> None:
    """
    Attach a measurement DataSet plus buffered (brcb01) and unbuffered (urcb01)
    Report Control Blocks to this LD's LLN0. RCBs allow MMS clients to
    subscribe to value-change reports.
    """
    # DataSet and RCB constructors take LogicalNode* directly, not ModelNode*.
    lln0 = iec61850.LogicalDevice_getLogicalNode(ld, "LLN0")
    if not lln0:
        return

    ds = iec61850.DataSet_create("MeasDS", lln0)

    # FCDA entries (libIEC61850 uses $-separated MMS-style paths here)
    fcda_paths = [
        f"{mmxu_name}$MX$TotW$mag$f",
        f"{mmxu_name}$MX$TotVAr$mag$f",
        f"{mmxu_name}$MX$TotVA$mag$f",
        f"{mmxu_name}$MX$Hz$mag$f",
        f"{mmxu_name}$MX$PhV$phsA$cVal$mag$f",
        f"{mmxu_name}$MX$PhV$phsB$cVal$mag$f",
        f"{mmxu_name}$MX$PhV$phsC$cVal$mag$f",
        f"{mmxu_name}$MX$A$phsA$cVal$mag$f",
        f"{mmxu_name}$MX$A$phsB$cVal$mag$f",
        f"{mmxu_name}$MX$A$phsC$cVal$mag$f",
    ]
    for fcda in fcda_paths:
        iec61850.DataSetEntry_create(ds, fcda, -1, None)

    # Buffered RCB
    iec61850.ReportControlBlock_create(
        "brcb01", lln0, "brcb01", True,
        "MeasDS", 1,
        TRG_DATA_CHANGED | TRG_INTEGRITY | TRG_GI | TRG_QCHG,
        RPT_SEQ | RPT_TS | RPT_REASON | RPT_DS | RPT_CONF_REV | RPT_ENTRY_ID,
        50, 1000,
    )

    # Unbuffered RCB
    iec61850.ReportControlBlock_create(
        "urcb01", lln0, "urcb01", False,
        "MeasDS", 1,
        TRG_DATA_CHANGED | TRG_GI,
        RPT_SEQ | RPT_TS | RPT_REASON,
        50, 0,
    )


# ---------------------------------------------------------------
# Reference → DataAttribute resolver
# ---------------------------------------------------------------
def _resolve_attributes(model: Any, do_refs: list[tuple[str, str]]) -> dict[str, Any]:
    """
    For each (DO_reference, CDC) tuple, look up every well-known sub-attribute
    via IedModel_getModelNodeByObjectReference and add it to the cache.
    """
    cache: dict[str, Any] = {}
    DATA_ATTRIBUTE_TYPE = 3  # ModelNodeType enum value

    for do_ref, cdc in do_refs:
        sub_paths = CDC_SUB_ATTRS.get(cdc, [])
        for sub in sub_paths:
            full_ref = f"{do_ref}.{sub}"
            try:
                node = iec61850.IedModel_getModelNodeByShortObjectReference(model, full_ref)
                if node is None:
                    continue
                # Only accept DataAttribute leaf nodes
                try:
                    if iec61850.ModelNode_getType(node) != DATA_ATTRIBUTE_TYPE:
                        continue
                except Exception:
                    pass
                cache[full_ref] = iec61850.toDataAttribute(node)
            except Exception:
                continue

    return cache
