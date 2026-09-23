import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nms_common.enums import AlertSeverity, AlertStatus, DeviceStatus, DeviceType, MetricType
from nms_common.models import Alert, Device, Interface, InterfaceMetric, Metric, WorkerHeartbeat

from app.deps import get_current_user, get_db
from app.schemas.dashboard import ChartPoint, ChartSeries, DashboardSummary, DeviceStatusDistribution

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_user)])


def _device_filters(
    location_id: uuid.UUID | None, device_type: DeviceType | None, vendor: str | None, status_filter: DeviceStatus | None
) -> list:
    conditions = []
    if location_id:
        conditions.append(Device.location_id == location_id)
    if device_type:
        conditions.append(Device.device_type == device_type)
    if vendor:
        conditions.append(Device.vendor == vendor)
    if status_filter:
        conditions.append(Device.status == status_filter)
    return conditions


@router.get("/summary", response_model=DashboardSummary)
async def dashboard_summary(
    db: AsyncSession = Depends(get_db),
    location_id: uuid.UUID | None = None,
    device_type: DeviceType | None = None,
    vendor: str | None = None,
    status_filter: DeviceStatus | None = Query(default=None, alias="status"),
) -> DashboardSummary:
    filters = _device_filters(location_id, device_type, vendor, status_filter)

    status_rows = (
        await db.execute(select(Device.status, func.count(Device.id)).where(*filters).group_by(Device.status))
    ).all()
    counts = {row[0]: row[1] for row in status_rows}
    total = sum(counts.values())

    device_ids_subq = select(Device.id).where(*filters).subquery()

    latest_metric_subq = (
        select(Metric.device_id, Metric.metric_type, Metric.value)
        .distinct(Metric.device_id, Metric.metric_type)
        .where(Metric.device_id.in_(select(device_ids_subq.c.id)))
        .order_by(Metric.device_id, Metric.metric_type, Metric.time.desc())
        .subquery()
    )
    metric_avgs = (
        await db.execute(
            select(
                func.avg(case((latest_metric_subq.c.metric_type == MetricType.AVAILABILITY, latest_metric_subq.c.value))),
                func.avg(case((latest_metric_subq.c.metric_type == MetricType.RESPONSE_TIME, latest_metric_subq.c.value))),
                func.avg(case((latest_metric_subq.c.metric_type == MetricType.PACKET_LOSS, latest_metric_subq.c.value))),
            )
        )
    ).one()
    avg_availability, avg_latency, avg_packet_loss = metric_avgs

    interface_ids_subq = select(Interface.id).where(Interface.device_id.in_(select(device_ids_subq.c.id))).subquery()
    latest_ifmetric_subq = (
        select(InterfaceMetric.in_bps, InterfaceMetric.out_bps)
        .distinct(InterfaceMetric.interface_id)
        .where(InterfaceMetric.interface_id.in_(select(interface_ids_subq.c.id)))
        .order_by(InterfaceMetric.interface_id, InterfaceMetric.time.desc())
        .subquery()
    )
    bw_row = (
        await db.execute(select(func.sum(latest_ifmetric_subq.c.in_bps), func.sum(latest_ifmetric_subq.c.out_bps)))
    ).one()

    alert_counts = (
        await db.execute(
            select(func.count(Alert.id), func.count(Alert.id).filter(Alert.severity == AlertSeverity.CRITICAL))
            .select_from(Alert)
            .join(Device, Device.id == Alert.device_id)
            .where(Alert.status != AlertStatus.RESOLVED, *filters)
        )
    ).one()

    heartbeat = (await db.execute(select(func.max(WorkerHeartbeat.last_heartbeat_at)))).scalar()

    return DashboardSummary(
        total_devices=total,
        online=counts.get(DeviceStatus.UP, 0),
        warning=counts.get(DeviceStatus.WARNING, 0),
        critical=counts.get(DeviceStatus.CRITICAL, 0),
        offline=counts.get(DeviceStatus.DOWN, 0),
        unknown=counts.get(DeviceStatus.UNKNOWN, 0),
        overall_availability_pct=round(avg_availability, 2) if avg_availability is not None else 0.0,
        active_alerts=alert_counts[0],
        active_critical_alerts=alert_counts[1],
        avg_latency_ms=round(avg_latency, 2) if avg_latency is not None else None,
        avg_packet_loss_pct=round(avg_packet_loss, 2) if avg_packet_loss is not None else None,
        total_inbound_bps=bw_row[0],
        total_outbound_bps=bw_row[1],
        worker_last_heartbeat_at=heartbeat,
    )


@router.get("/status-distribution", response_model=list[DeviceStatusDistribution])
async def status_distribution(
    db: AsyncSession = Depends(get_db),
    location_id: uuid.UUID | None = None,
    device_type: DeviceType | None = None,
    vendor: str | None = None,
) -> list[DeviceStatusDistribution]:
    filters = _device_filters(location_id, device_type, vendor, None)
    rows = (
        await db.execute(select(Device.status, func.count(Device.id)).where(*filters).group_by(Device.status))
    ).all()
    return [DeviceStatusDistribution(status=row[0].value, count=row[1]) for row in rows]


@router.get("/charts/{series}", response_model=ChartSeries)
async def dashboard_chart(
    series: str,
    db: AsyncSession = Depends(get_db),
    hours: int = Query(default=24, le=24 * 30),
) -> ChartSeries:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    bucket = func.date_trunc("hour", Metric.time).label("bucket")

    metric_map = {
        "latency": MetricType.RESPONSE_TIME,
        "availability": MetricType.AVAILABILITY,
        "packet-loss": MetricType.PACKET_LOSS,
    }

    if series in metric_map:
        rows = (
            await db.execute(
                select(bucket, func.avg(Metric.value))
                .where(Metric.metric_type == metric_map[series], Metric.time >= since)
                .group_by(bucket)
                .order_by(bucket)
            )
        ).all()
        return ChartSeries(label=series, points=[ChartPoint(time=r[0], value=float(r[1])) for r in rows])

    if series == "bandwidth":
        bw_bucket = func.date_trunc("hour", InterfaceMetric.time).label("bucket")
        rows = (
            await db.execute(
                select(bw_bucket, func.avg(InterfaceMetric.in_bps + InterfaceMetric.out_bps))
                .where(InterfaceMetric.time >= since)
                .group_by(bw_bucket)
                .order_by(bw_bucket)
            )
        ).all()
        return ChartSeries(label="bandwidth", points=[ChartPoint(time=r[0], value=float(r[1] or 0)) for r in rows])

    if series == "alert-trend":
        alert_bucket = func.date_trunc("hour", Alert.opened_at).label("bucket")
        rows = (
            await db.execute(
                select(alert_bucket, func.count(Alert.id))
                .where(Alert.opened_at >= since)
                .group_by(alert_bucket)
                .order_by(alert_bucket)
            )
        ).all()
        return ChartSeries(label="alert-trend", points=[ChartPoint(time=r[0], value=float(r[1])) for r in rows])

    return ChartSeries(label=series, points=[])
