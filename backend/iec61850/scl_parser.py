"""
SCL (Substation Configuration Language) XML parser.
Supports ICD, CID, and SCD file formats per IEC 61850-6.

Returns a ParsedSCL dataclass containing all IEDs with their logical
device and logical node structure, resolved against DataTypeTemplates.
"""
from __future__ import annotations
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

SCL_NS = "http://www.iec.ch/61850/2003/SCL"
NS = f"{{{SCL_NS}}}"


@dataclass
class ParsedDA:
    name: str
    btype: str
    fc: str
    type_ref: Optional[str] = None
    count: int = 0


@dataclass
class ParsedDOType:
    id: str
    cdc: str
    das: list[ParsedDA] = field(default_factory=list)


@dataclass
class ParsedDO:
    name: str
    type_ref: str


@dataclass
class ParsedLN:
    ln_class: str
    inst: str
    prefix: str
    type_ref: str
    data_objects: list[ParsedDO] = field(default_factory=list)


@dataclass
class ParsedLD:
    inst: str
    logical_nodes: list[ParsedLN] = field(default_factory=list)


@dataclass
class ParsedIED:
    name: str
    logical_devices: list[ParsedLD] = field(default_factory=list)


@dataclass
class ParsedSCL:
    ieds: list[ParsedIED] = field(default_factory=list)
    lnode_types: dict[str, list[ParsedDO]] = field(default_factory=dict)
    do_types: dict[str, ParsedDOType] = field(default_factory=dict)
    da_types: dict[str, list[ParsedDA]] = field(default_factory=dict)


def parse_scl(xml_bytes: bytes) -> ParsedSCL:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid XML: {exc}") from exc

    # Normalize namespace: support both namespaced and non-namespaced SCL
    if root.tag.startswith("{"):
        _ns = root.tag.split("}")[0][1:]
        ns_prefix = f"{{{_ns}}}"
    else:
        ns_prefix = ""

    result = ParsedSCL()

    dt_elem = root.find(f"{ns_prefix}DataTypeTemplates")
    if dt_elem is not None:
        result.lnode_types, result.do_types, result.da_types = _parse_data_type_templates(
            dt_elem, ns_prefix
        )

    for ied_elem in root.findall(f"{ns_prefix}IED"):
        ied = _parse_ied(ied_elem, ns_prefix, result.lnode_types)
        result.ieds.append(ied)

    return result


def _parse_data_type_templates(
    dt: ET.Element, ns: str
) -> tuple[dict, dict, dict]:
    lnode_types: dict[str, list[ParsedDO]] = {}
    do_types: dict[str, ParsedDOType] = {}
    da_types: dict[str, list[ParsedDA]] = {}

    for ln_type in dt.findall(f"{ns}LNodeType"):
        type_id = ln_type.get("id", "")
        dos: list[ParsedDO] = []
        for do_elem in ln_type.findall(f"{ns}DO"):
            dos.append(ParsedDO(
                name=do_elem.get("name", ""),
                type_ref=do_elem.get("type", ""),
            ))
        lnode_types[type_id] = dos

    for do_type in dt.findall(f"{ns}DOType"):
        type_id = do_type.get("id", "")
        cdc = do_type.get("cdc", "")
        das: list[ParsedDA] = []
        for da_elem in do_type.findall(f"{ns}DA"):
            das.append(ParsedDA(
                name=da_elem.get("name", ""),
                btype=da_elem.get("bType", ""),
                fc=da_elem.get("fc", ""),
                type_ref=da_elem.get("type"),
                count=int(da_elem.get("count", "0") or "0"),
            ))
        do_types[type_id] = ParsedDOType(id=type_id, cdc=cdc, das=das)

    for da_type in dt.findall(f"{ns}DAType"):
        type_id = da_type.get("id", "")
        bdas: list[ParsedDA] = []
        for bda in da_type.findall(f"{ns}BDA"):
            bdas.append(ParsedDA(
                name=bda.get("name", ""),
                btype=bda.get("bType", ""),
                fc="",
                type_ref=bda.get("type"),
            ))
        da_types[type_id] = bdas

    return lnode_types, do_types, da_types


def _parse_ied(
    ied_elem: ET.Element,
    ns: str,
    lnode_types: dict[str, list[ParsedDO]],
) -> ParsedIED:
    ied = ParsedIED(name=ied_elem.get("name", "IED"))

    for ap in ied_elem.findall(f"{ns}AccessPoint"):
        server = ap.find(f"{ns}Server")
        if server is None:
            continue
        for ld_elem in server.findall(f"{ns}LDevice"):
            ld = ParsedLD(inst=ld_elem.get("inst", ""))
            # LN0 first
            lln0 = ld_elem.find(f"{ns}LN0")
            if lln0 is not None:
                ld.logical_nodes.append(_parse_ln(lln0, ns, lnode_types, "LLN0"))
            for ln_elem in ld_elem.findall(f"{ns}LN"):
                ln_class = ln_elem.get("lnClass", "")
                ld.logical_nodes.append(_parse_ln(ln_elem, ns, lnode_types, ln_class))
            ied.logical_devices.append(ld)

    return ied


def _parse_ln(
    ln_elem: ET.Element,
    ns: str,
    lnode_types: dict[str, list[ParsedDO]],
    ln_class: str,
) -> ParsedLN:
    type_ref = ln_elem.get("lnType", "")
    ln = ParsedLN(
        ln_class=ln_class,
        inst=ln_elem.get("inst", ""),
        prefix=ln_elem.get("prefix", ""),
        type_ref=type_ref,
        data_objects=lnode_types.get(type_ref, []),
    )
    return ln
