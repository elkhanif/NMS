import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nms_common.config import get_settings
from nms_common.db import new_session
from nms_common.enums import CheckType, CredentialType, MetricType
from nms_common.models import Device, DeviceCheck, DeviceCredential
from nms_common.ws_events import publish_pending

from worker import alert_engine, collectors
from worker.credentials import decrypt_credential
from worker.pollers.http import poll_http
from worker.pollers.icmp import poll_icmp
from worker.pollers.snmp import build_auth_data, poll_snmp_device
from worker.pollers.tcp import poll_tcp

logger = logging.getLogger("worker.scheduler")


class Scheduler:
    """Reconciles running poll tasks against `device_checks` every RECONCILE_INTERVAL
    seconds, then lets each (device, check) run its own independent async loop at its
    own interval. One bad device/check can only ever crash its own loop -- the
    reconcile pass just restarts it next cycle -- never the scheduler itself."""

    RECONCILE_INTERVAL = 15

    def __init__(self) -> None:
        self.settings = get_settings()
        self.semaphore = asyncio.Semaphore(self.settings.max_concurrent_polls)
        self._tasks: dict[tuple[uuid.UUID, uuid.UUID], asyncio.Task] = {}
        self.active_devices = 0
        self.active_polls = 0

    async def run_forever(self) -> None:
        while True:
            try:
                await self._reconcile()
            except Exception:
                logger.exception("Error reconciling device checks")
            await asyncio.sleep(self.RECONCILE_INTERVAL)

    async def _reconcile(self) -> None:
        async with new_session() as db:
            result = await db.execute(
                select(Device).where(Device.is_monitored.is_(True)).options(selectinload(Device.checks))
            )
            devices = list(result.scalars().all())

        self.active_devices = len(devices)
        wanted: set[tuple[uuid.UUID, uuid.UUID]] = set()
        for device in devices:
            for check in device.checks:
                if not check.enabled:
                    continue
                key = (device.id, check.id)
                wanted.add(key)
                if key not in self._tasks or self._tasks[key].done():
                    self._tasks[key] = asyncio.create_task(self._check_loop(device.id, check.id))

        for key in list(self._tasks):
            if key not in wanted:
                self._tasks.pop(key).cancel()

    async def _check_loop(self, device_id: uuid.UUID, check_id: uuid.UUID) -> None:
        interval = self.settings.default_interval_normal
        while True:
            try:
                async with new_session() as db:
                    device = await db.get(Device, device_id)
                    check = await db.get(DeviceCheck, check_id)
                    if device is None or check is None or not device.is_monitored or not check.enabled:
                        return
                    interval = check.interval_seconds
                    await self._poll_once(db, device, check)
                    await db.commit()
                    await publish_pending(db)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Poll failed for device=%s check=%s", device_id, check_id)
            await asyncio.sleep(interval)

    async def _poll_once(self, db: AsyncSession, device: Device, check: DeviceCheck) -> None:
        attempts = max(1, check.retries + 1)
        result: dict = {"reachable": False}
        for _ in range(attempts):
            async with self.semaphore:
                self.active_polls += 1
                try:
                    result = await asyncio.wait_for(self._dispatch(db, device, check), timeout=check.timeout_seconds)
                except Exception as exc:  # noqa: BLE001 -- a bad/unreachable device must never kill the loop
                    result = {"reachable": False, "error": str(exc)}
                finally:
                    self.active_polls -= 1
            if result.get("reachable"):
                break

        previous_status = device.status
        await self._collect(db, device, check, result)
        await collectors.record_state_transition(db, device, previous_status)

        if result.get("reachable"):
            observed_mac = None
            if check.check_type == CheckType.SNMP:
                interfaces_with_mac = sorted(
                    (i for i in result.get("interfaces", []) if i.get("mac_address")),
                    key=lambda i: i.get("if_index", 0),
                )
                if interfaces_with_mac:
                    observed_mac = interfaces_with_mac[0]["mac_address"]
            await collectors.record_address_observation(db, device, observed_mac=observed_mac)

    async def _dispatch(self, db: AsyncSession, device: Device, check: DeviceCheck) -> dict:
        if check.check_type == CheckType.ICMP:
            return await poll_icmp(device.ip_address, timeout=check.timeout_seconds)

        if check.check_type == CheckType.TCP:
            port = int(check.config.get("port", 80))
            return await poll_tcp(device.ip_address, port, timeout=check.timeout_seconds)

        if check.check_type in (CheckType.HTTP, CheckType.HTTPS):
            scheme = "https" if check.check_type == CheckType.HTTPS else "http"
            path = check.config.get("path", "/")
            port = check.config.get("port")
            port_part = f":{port}" if port else ""
            url = f"{scheme}://{device.ip_address}{port_part}{path}"
            return await poll_http(url, timeout=check.timeout_seconds, expected_status=check.config.get("expected_status", 200))

        if check.check_type == CheckType.SNMP:
            credential = await self._get_credential(db, device.id, CredentialType.SNMPV3)
            if credential is None:
                credential = await self._get_credential(db, device.id, CredentialType.SNMPV2C)
            if credential is None:
                return {"reachable": False, "error": "no SNMP credential configured"}
            payload = decrypt_credential(credential)
            auth = build_auth_data(credential.credential_type, payload)
            port = int(check.config.get("port", 161))
            data = await poll_snmp_device(device.ip_address, auth, port=port, timeout=check.timeout_seconds)
            data["reachable"] = bool(data.get("sys_descr")) or bool(data.get("interfaces"))
            return data

        return {"reachable": False, "error": "unsupported check type"}

    async def _get_credential(
        self, db: AsyncSession, device_id: uuid.UUID, credential_type: CredentialType
    ) -> DeviceCredential | None:
        result = await db.execute(
            select(DeviceCredential).where(
                DeviceCredential.device_id == device_id, DeviceCredential.credential_type == credential_type
            )
        )
        return result.scalar_one_or_none()

    async def _collect(self, db: AsyncSession, device: Device, check: DeviceCheck, result: dict) -> None:
        reachable = bool(result.get("reachable"))

        if check.check_type == CheckType.ICMP:
            collectors.record_metric(db, device.id, MetricType.AVAILABILITY, 100.0 if reachable else 0.0, "%")
            if result.get("avg_rtt_ms") is not None:
                collectors.record_metric(db, device.id, MetricType.RESPONSE_TIME, result["avg_rtt_ms"], "ms")
            if result.get("packet_loss_pct") is not None:
                collectors.record_metric(db, device.id, MetricType.PACKET_LOSS, result["packet_loss_pct"], "%")
                await alert_engine.evaluate_metric_rules(db, device, MetricType.PACKET_LOSS, result["packet_loss_pct"])
            await collectors.update_reachability(db, device, reachable)

        elif check.check_type == CheckType.TCP:
            collectors.record_metric(db, device.id, MetricType.AVAILABILITY, 100.0 if reachable else 0.0, "%")
            if result.get("response_time_ms") is not None:
                collectors.record_metric(db, device.id, MetricType.RESPONSE_TIME, result["response_time_ms"], "ms")
            if check.config.get("primary_reachability_check", True):
                await collectors.update_reachability(db, device, reachable)

        elif check.check_type in (CheckType.HTTP, CheckType.HTTPS):
            collectors.record_metric(db, device.id, MetricType.AVAILABILITY, 100.0 if reachable else 0.0, "%")
            if result.get("response_time_ms") is not None:
                collectors.record_metric(db, device.id, MetricType.RESPONSE_TIME, result["response_time_ms"], "ms")

        elif check.check_type == CheckType.SNMP:
            if result.get("cpu_percent") is not None:
                collectors.record_metric(db, device.id, MetricType.CPU_USAGE, result["cpu_percent"], "%")
                await alert_engine.evaluate_metric_rules(db, device, MetricType.CPU_USAGE, result["cpu_percent"])
            if result.get("memory_percent") is not None:
                collectors.record_metric(db, device.id, MetricType.MEMORY_USAGE, result["memory_percent"], "%")
                await alert_engine.evaluate_metric_rules(db, device, MetricType.MEMORY_USAGE, result["memory_percent"])
            if result.get("disk_percent") is not None:
                collectors.record_metric(db, device.id, MetricType.DISK_USAGE, result["disk_percent"], "%")
            if result.get("uptime_seconds") is not None:
                collectors.record_metric(db, device.id, MetricType.UPTIME, result["uptime_seconds"], "s")
            await collectors.sync_interfaces(db, device, result.get("interfaces", []))

        await collectors.refresh_device_status(db, device)
