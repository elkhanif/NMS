import uuid

from nms_common.enums import AlertOperator

from worker import state
from worker.alert_engine import _compare


def test_compare_operators():
    assert _compare(90, AlertOperator.GT, 80) is True
    assert _compare(80, AlertOperator.GT, 80) is False
    assert _compare(80, AlertOperator.GTE, 80) is True
    assert _compare(10, AlertOperator.LT, 20) is True
    assert _compare(20, AlertOperator.LTE, 20) is True
    assert _compare(5, AlertOperator.EQ, 5) is True


def test_hysteresis_breach_then_recover():
    key = (uuid.uuid4(), uuid.uuid4())

    assert state.record_breach(key) == 1
    assert state.record_breach(key) == 2
    assert state.record_breach(key) == 3

    # a single OK poll resets the breach streak entirely (anti-flapping)
    assert state.record_ok(key) == 1
    assert state.record_ok(key) == 2

    assert state.record_breach(key) == 1
