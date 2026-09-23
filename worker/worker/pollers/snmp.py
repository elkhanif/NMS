"""SNMPv2c and SNMPv3 polling via pysnmp's asyncio hlapi (pysnmp>=6.2).

NOTE: pysnmp's async API has moved around across major versions. If SNMP polling
raises AttributeError/ImportError at startup, this is the first file to check against
whatever `pysnmp` version actually resolved in the container -- everything else in the
worker only depends on the plain-dict return shape of `poll_snmp_device`, so a version
fixup is isolated to this module.

Known limitation: `poll_snmp_device` makes ~17 sequential snmp_get/snmp_walk calls, so
a target that's merely slow (not down) on every one of them could in the worst case
need more wall-clock time than a single check's configured timeout, since the
scheduler wraps the whole dispatch in one `asyncio.wait_for(..., timeout=check.timeout_seconds)`.
`snmp_walk`'s own wall-clock deadline (see below) at least guarantees no single walk
can run away past that budget on its own: without it, the bundled `mock-snmp` dev
fixture's ifAlias table (which never hits a subtree boundary -- some snmpsim variation
modules synthesize values for arbitrarily large indices) burned the full 2000-iteration
cap on every poll, ~27s for that one walk alone. A real device's finitely-sized table
hits the boundary within the first GETBULK response either way, so this doesn't change
behavior against real gear -- it only bounds the pathological case.
"""

import time

from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    bulk_cmd,
    get_cmd,
    usm3DESEDEPrivProtocol,
    usmAesCfb128Protocol,
    usmAesCfb192Protocol,
    usmAesCfb256Protocol,
    usmDESPrivProtocol,
    usmHMAC128SHA224AuthProtocol,
    usmHMAC192SHA256AuthProtocol,
    usmHMAC256SHA384AuthProtocol,
    usmHMAC384SHA512AuthProtocol,
    usmHMACMD5AuthProtocol,
    usmHMACSHAAuthProtocol,
)

from nms_common.enums import CredentialType

AUTH_PROTOCOLS = {
    "MD5": usmHMACMD5AuthProtocol,
    "SHA": usmHMACSHAAuthProtocol,
    "SHA1": usmHMACSHAAuthProtocol,
    "SHA224": usmHMAC128SHA224AuthProtocol,
    "SHA256": usmHMAC192SHA256AuthProtocol,
    "SHA384": usmHMAC256SHA384AuthProtocol,
    "SHA512": usmHMAC384SHA512AuthProtocol,
}

PRIV_PROTOCOLS = {
    "DES": usmDESPrivProtocol,
    "3DES": usm3DESEDEPrivProtocol,
    "AES": usmAesCfb128Protocol,
    "AES128": usmAesCfb128Protocol,
    "AES192": usmAesCfb192Protocol,
    "AES256": usmAesCfb256Protocol,
}


def build_auth_data(credential_type: CredentialType, payload: dict):
    """Builds the pysnmp auth object for a poll/probe from a decrypted credential
    payload.

    SNMPv2c payload: {"community": str}.
    SNMPv3 payload: {"username": str, "auth_protocol": str | None,
    "auth_password": str | None, "priv_protocol": str | None, "priv_password": str | None}
    -- security level (noAuthNoPriv/authNoPriv/authPriv) follows from which of those
    are present, same as any USM implementation, so nothing else needs to track it.
    """
    if credential_type == CredentialType.SNMPV3:
        kwargs = {}
        auth_protocol = AUTH_PROTOCOLS.get((payload.get("auth_protocol") or "").upper())
        if auth_protocol is not None:
            kwargs["authProtocol"] = auth_protocol
        priv_protocol = PRIV_PROTOCOLS.get((payload.get("priv_protocol") or "").upper())
        if priv_protocol is not None:
            kwargs["privProtocol"] = priv_protocol
        return UsmUserData(
            payload["username"],
            authKey=payload.get("auth_password") or None,
            privKey=payload.get("priv_password") or None,
            **kwargs,
        )
    return CommunityData(payload.get("community", "public"), mpModel=1)


# Standard MIB-II / HOST-RESOURCES-MIB OIDs
OID_SYS_DESCR = "1.3.6.1.2.1.1.1.0"
OID_SYS_UPTIME = "1.3.6.1.2.1.1.3.0"
OID_HR_PROCESSOR_LOAD = "1.3.6.1.2.1.25.3.3.1.2"
OID_HR_STORAGE_DESCR = "1.3.6.1.2.1.25.2.3.1.3"
OID_HR_STORAGE_ALLOC_UNITS = "1.3.6.1.2.1.25.2.3.1.4"
OID_HR_STORAGE_SIZE = "1.3.6.1.2.1.25.2.3.1.5"
OID_HR_STORAGE_USED = "1.3.6.1.2.1.25.2.3.1.6"

# IF-MIB / IF-MIB extension table (ifXTable)
OID_IF_DESCR = "1.3.6.1.2.1.2.2.1.2"
OID_IF_ADMIN_STATUS = "1.3.6.1.2.1.2.2.1.7"
OID_IF_OPER_STATUS = "1.3.6.1.2.1.2.2.1.8"
OID_IF_IN_OCTETS = "1.3.6.1.2.1.2.2.1.10"
OID_IF_IN_ERRORS = "1.3.6.1.2.1.2.2.1.14"
OID_IF_IN_DISCARDS = "1.3.6.1.2.1.2.2.1.13"
OID_IF_OUT_OCTETS = "1.3.6.1.2.1.2.2.1.16"
OID_IF_OUT_ERRORS = "1.3.6.1.2.1.2.2.1.20"
OID_IF_OUT_DISCARDS = "1.3.6.1.2.1.2.2.1.19"
OID_IF_SPEED = "1.3.6.1.2.1.2.2.1.5"
OID_IF_PHYS_ADDRESS = "1.3.6.1.2.1.2.2.1.6"
OID_IF_ALIAS = "1.3.6.1.2.1.31.1.1.1.18"
OID_IF_HC_IN_OCTETS = "1.3.6.1.2.1.31.1.1.1.6"
OID_IF_HC_OUT_OCTETS = "1.3.6.1.2.1.31.1.1.1.10"

INTERFACE_STATUS_MAP = {1: "UP", 2: "DOWN", 3: "TESTING"}


async def _build_transport(ip: str, port: int, timeout: float, retries: int) -> UdpTransportTarget:
    try:
        return await UdpTransportTarget.create((ip, port), timeout=timeout, retries=retries)
    except TypeError:
        return UdpTransportTarget((ip, port), timeout=timeout, retries=retries)


async def snmp_get(ip: str, auth, oids: list[str], port: int = 161, timeout: float = 5.0) -> dict:
    engine = SnmpEngine()
    transport = await _build_transport(ip, port, timeout, retries=1)

    error_indication, error_status, _error_index, var_binds = await get_cmd(
        engine, auth, transport, ContextData(), *(ObjectType(ObjectIdentity(oid)) for oid in oids)
    )
    if error_indication or error_status:
        raise ConnectionError(str(error_indication or error_status.prettyPrint()))

    return {str(name): value for name, value in var_binds}


async def snmp_walk(ip: str, auth, base_oid: str, port: int = 161, timeout: float = 5.0) -> dict:
    """Walks a subtree using repeated GETNEXT (simpler/more portable across pysnmp
    versions than paginated GETBULK); fine for IF-MIB-sized tables on office/home gear."""
    engine = SnmpEngine()
    transport = await _build_transport(ip, port, timeout, retries=1)

    results: dict[str, object] = {}
    current_oid = base_oid
    deadline = time.monotonic() + timeout
    for _ in range(2000):  # hard cap so a misbehaving agent can't loop the worker forever
        if time.monotonic() > deadline:
            break
        error_indication, error_status, _error_index, var_binds = await bulk_cmd(
            engine, auth, transport, ContextData(), 0, 25, ObjectType(ObjectIdentity(current_oid))
        )
        if error_indication or error_status:
            break

        advanced = False
        for name, value in var_binds:
            oid_str = str(name)
            if not oid_str.startswith(base_oid + ".") and oid_str != base_oid:
                return results
            results[oid_str] = value
            current_oid = oid_str
            advanced = True
        if not advanced:
            break

    return results


def _last_index(oid: str) -> str:
    return oid.rsplit(".", 1)[-1]


def _format_mac(value: object) -> str | None:
    """ifPhysAddress comes back as a 6-byte OCTET STRING; format it the same
    aa:bb:cc:dd:ee:ff way as everything else in this app expects."""
    try:
        raw = bytes(value)
    except Exception:
        return None
    if len(raw) != 6:
        return None
    return ":".join(f"{b:02x}" for b in raw)


async def poll_snmp_device(ip: str, auth, port: int = 161, timeout: float = 5.0) -> dict:
    """Returns sys info, CPU/memory/disk (best-effort, agent-dependent), and interfaces."""
    sys_info = await snmp_get(ip, auth, [OID_SYS_DESCR, OID_SYS_UPTIME], port, timeout)

    cpu_percent = None
    try:
        cpu_table = await snmp_walk(ip, auth, OID_HR_PROCESSOR_LOAD, port, timeout)
        loads = [float(v) for v in cpu_table.values()]
        if loads:
            cpu_percent = sum(loads) / len(loads)
    except Exception:
        pass

    memory_percent = None
    disk_percent = None
    try:
        descr_table = await snmp_walk(ip, auth, OID_HR_STORAGE_DESCR, port, timeout)
        size_table = await snmp_walk(ip, auth, OID_HR_STORAGE_SIZE, port, timeout)
        used_table = await snmp_walk(ip, auth, OID_HR_STORAGE_USED, port, timeout)

        for oid, descr in descr_table.items():
            idx = _last_index(oid)
            size_oid = f"{OID_HR_STORAGE_SIZE}.{idx}"
            used_oid = f"{OID_HR_STORAGE_USED}.{idx}"
            size = size_table.get(size_oid)
            used = used_table.get(used_oid)
            if not size or int(size) == 0:
                continue
            pct = (int(used) / int(size)) * 100
            descr_str = str(descr).lower()
            if "physical memory" in descr_str or "ram" in descr_str:
                memory_percent = pct
            elif descr_str in ("/", "c:\\ label:  serial number") or descr_str.startswith("/"):
                disk_percent = pct
    except Exception:
        pass

    interfaces: dict[str, dict] = {}
    try:
        for table_oid, key in [
            (OID_IF_DESCR, "name"),
            (OID_IF_ALIAS, "alias"),
            (OID_IF_ADMIN_STATUS, "admin_status"),
            (OID_IF_OPER_STATUS, "oper_status"),
            (OID_IF_SPEED, "speed_bps"),
            (OID_IF_PHYS_ADDRESS, "mac_address"),
            (OID_IF_HC_IN_OCTETS, "in_octets"),
            (OID_IF_HC_OUT_OCTETS, "out_octets"),
            (OID_IF_IN_ERRORS, "errors_in"),
            (OID_IF_OUT_ERRORS, "errors_out"),
            (OID_IF_IN_DISCARDS, "discards_in"),
            (OID_IF_OUT_DISCARDS, "discards_out"),
        ]:
            table = await snmp_walk(ip, auth, table_oid, port, timeout)
            for oid, value in table.items():
                if_index = _last_index(oid)
                interfaces.setdefault(if_index, {"if_index": int(if_index)})[key] = value

        for if_index, iface in interfaces.items():
            if "in_octets" not in iface:
                fallback = await snmp_walk(ip, auth, OID_IF_IN_OCTETS, port, timeout)
                iface["in_octets"] = fallback.get(f"{OID_IF_IN_OCTETS}.{if_index}")
            if "out_octets" not in iface:
                fallback = await snmp_walk(ip, auth, OID_IF_OUT_OCTETS, port, timeout)
                iface["out_octets"] = fallback.get(f"{OID_IF_OUT_OCTETS}.{if_index}")
            if "admin_status" in iface:
                iface["admin_status"] = INTERFACE_STATUS_MAP.get(int(iface["admin_status"]), "UNKNOWN")
            if "oper_status" in iface:
                iface["oper_status"] = INTERFACE_STATUS_MAP.get(int(iface["oper_status"]), "UNKNOWN")
            for numeric_field in ("speed_bps", "in_octets", "out_octets", "errors_in", "errors_out", "discards_in", "discards_out"):
                if iface.get(numeric_field) is not None:
                    try:
                        iface[numeric_field] = int(iface[numeric_field])
                    except (TypeError, ValueError):
                        iface[numeric_field] = None
            if "name" in iface:
                iface["name"] = str(iface["name"])
            if "alias" in iface:
                iface["alias"] = str(iface["alias"])
            if "mac_address" in iface:
                iface["mac_address"] = _format_mac(iface["mac_address"])
    except Exception:
        pass

    uptime_ticks = sys_info.get(OID_SYS_UPTIME)
    sys_descr = sys_info.get(OID_SYS_DESCR)

    return {
        "sys_descr": str(sys_descr) if sys_descr is not None else None,
        "uptime_seconds": (int(uptime_ticks) / 100) if uptime_ticks is not None else None,
        "cpu_percent": cpu_percent,
        "memory_percent": memory_percent,
        "disk_percent": disk_percent,
        "interfaces": list(interfaces.values()),
    }
