import asyncio
import ipaddress
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from nms_common.config import get_settings
from nms_common.db import new_session
from nms_common.enums import CredentialType, DeviceType, DiscoveryJobStatus
from nms_common.models import DeviceCredential, DiscoveryJob, DiscoveryResult

from worker.credentials import decrypt_credential
from worker.pollers.icmp import poll_icmp
from worker.pollers.snmp import build_auth_data, poll_snmp_device
from worker.pollers.tcp import poll_tcp

logger = logging.getLogger("worker.discovery")

COMMON_PORTS = [22, 23, 80, 443, 161, 554, 9100, 3389]
POLL_INTERVAL = 5
MAX_CONCURRENT_PROBES = 20


async def run_forever() -> None:
    """Watches for administrator-triggered discovery jobs (created via the API) and
    executes them here, since the worker is the only component with network access."""
    while True:
        try:
            await _pick_up_pending_job()
        except Exception:
            logger.exception("Discovery loop error")
        await asyncio.sleep(POLL_INTERVAL)


async def _pick_up_pending_job() -> None:
    async with new_session() as db:
        result = await db.execute(
            select(DiscoveryJob)
            .where(DiscoveryJob.status == DiscoveryJobStatus.PENDING)
            .order_by(DiscoveryJob.created_at)
            .limit(1)
        )
        job = result.scalar_one_or_none()
        if job is None:
            return
        job.status = DiscoveryJobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job_id = job.id
        await db.commit()

    try:
        await _execute_job(job_id)
    except Exception:
        logger.exception("Discovery job %s failed", job_id)
        async with new_session() as db:
            job = await db.get(DiscoveryJob, job_id)
            if job is not None:
                job.status = DiscoveryJobStatus.FAILED
                job.error_message = "Discovery job failed; see worker logs for details"
                job.finished_at = datetime.now(timezone.utc)
                await db.commit()


async def _probe_host(ip: str, credential_type: CredentialType | None, credential_payload: dict | None) -> dict | None:
    icmp_result = await poll_icmp(ip, timeout=1.0, count=1)
    open_ports: list[int] = []
    for port in COMMON_PORTS:
        tcp_result = await poll_tcp(ip, port, timeout=0.75)
        if tcp_result.get("reachable"):
            open_ports.append(port)

    if not icmp_result.get("reachable") and not open_ports:
        return None

    snmp_reachable = False
    sys_descr = ""
    if 161 in open_ports and credential_payload and credential_type is not None:
        try:
            auth = build_auth_data(credential_type, credential_payload)
            snmp_data = await poll_snmp_device(ip, auth, timeout=1.5)
            sys_descr = (snmp_data.get("sys_descr") or "").lower()
            snmp_reachable = bool(sys_descr)
        except Exception:
            pass

    if snmp_reachable and ("router" in sys_descr or "ios" in sys_descr):
        suggested = DeviceType.ROUTER
    elif snmp_reachable and "switch" in sys_descr:
        suggested = DeviceType.SWITCH
    elif 9100 in open_ports:
        suggested = DeviceType.PRINTER
    elif 554 in open_ports:
        suggested = DeviceType.CCTV_NVR
    elif 22 in open_ports or 3389 in open_ports:
        suggested = DeviceType.SERVER
    else:
        suggested = DeviceType.GENERIC

    return {
        "ip_address": ip,
        "open_ports": open_ports,
        "snmp_reachable": snmp_reachable,
        "suggested_device_type": suggested,
    }


async def _execute_job(job_id: uuid.UUID) -> None:
    settings = get_settings()

    async with new_session() as db:
        job = await db.get(DiscoveryJob, job_id)
        network = ipaddress.ip_network(job.cidr, strict=False)
        hosts = list(network.hosts()) if network.num_addresses > 1 else [network.network_address]
        hosts = hosts[: settings.discovery_max_hosts]
        job.total_hosts = len(hosts)

        credential_payload = None
        credential_type = None
        if job.credential_ref_id:
            credential = await db.get(DeviceCredential, job.credential_ref_id)
            if credential is not None and credential.credential_type in (
                CredentialType.SNMPV2C,
                CredentialType.SNMPV3,
            ):
                credential_payload = decrypt_credential(credential)
                credential_type = credential.credential_type

        rate_limit_pps = max(1, job.rate_limit_pps)
        await db.commit()

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_PROBES)

    async def bounded_probe(ip):
        async with semaphore:
            return await _probe_host(str(ip), credential_type, credential_payload)

    tasks = []
    for host in hosts:
        tasks.append(asyncio.create_task(bounded_probe(host)))
        await asyncio.sleep(1.0 / rate_limit_pps)  # paces how fast new probes are launched

    results = await asyncio.gather(*tasks, return_exceptions=True)

    found_count = 0
    async with new_session() as db:
        for res in results:
            if isinstance(res, Exception) or res is None:
                continue
            found_count += 1
            db.add(DiscoveryResult(discovery_job_id=job_id, hostname_guess=None, mac_address=None, **res))

        job = await db.get(DiscoveryJob, job_id)
        job.status = DiscoveryJobStatus.COMPLETED
        job.finished_at = datetime.now(timezone.utc)
        job.found_count = found_count
        await db.commit()
