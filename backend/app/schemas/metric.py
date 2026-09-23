from datetime import datetime

from pydantic import BaseModel

from nms_common.enums import MetricType


class MetricPoint(BaseModel):
    time: datetime
    value: float


class MetricSeries(BaseModel):
    metric_type: MetricType
    unit: str | None
    points: list[MetricPoint]


class InterfaceMetricPoint(BaseModel):
    time: datetime
    in_bps: float | None
    out_bps: float | None
    errors_in: int | None
    errors_out: int | None
    discards_in: int | None
    discards_out: int | None
