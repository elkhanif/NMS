"""network detective / what's happening: addresses, state history, incidents

Adds the data model for Network Detective and What's Happening: device IP/MAC
history (device_addresses), a structured device status transition log
(device_state_history), and incident correlation (incidents, incident_events),
plus devices.serial_number/default_gateway_ip and new change-detection EventType
values.

Written defensively (IF NOT EXISTS / checkfirst) rather than as a frozen diff,
because 0001_baseline's `Base.metadata.create_all` reflects whatever models are
*currently* registered at the time it runs -- so on a brand-new database it will
already create these same tables/columns as part of the baseline, while on this
already-migrated database none of them exist yet. Both must end up in the same
state without either path erroring.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-23

"""
import sqlalchemy as sa
from alembic import op

from nms_common.db import Base
from nms_common.models import DeviceAddress, DeviceStateHistory, Incident, IncidentEvent

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

_NEW_EVENT_TYPES = [
    "DEVICE_NEW",
    "DEVICE_MISSING",
    "IP_CHANGED",
    "MAC_CHANGED",
    "SWITCH_PORT_CHANGED",
    "VLAN_CHANGED",
    "GATEWAY_CHANGED",
    "AP_ASSOCIATION_CHANGED",
]


def upgrade() -> None:
    bind = op.get_bind()

    # ALTER TYPE ... ADD VALUE cannot run inside the migration's normal transaction
    # block in Postgres -- each needs its own auto-committed statement.
    with op.get_context().autocommit_block():
        for value in _NEW_EVENT_TYPES:
            bind.execute(sa.text(f"ALTER TYPE eventtype ADD VALUE IF NOT EXISTS '{value}'"))

    bind.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS incident_seq START 1"))

    bind.execute(sa.text("ALTER TABLE devices ADD COLUMN IF NOT EXISTS serial_number VARCHAR(255)"))
    bind.execute(sa.text("ALTER TABLE devices ADD COLUMN IF NOT EXISTS default_gateway_ip VARCHAR(45)"))

    Base.metadata.create_all(
        bind=bind,
        checkfirst=True,
        tables=[
            DeviceAddress.__table__,
            DeviceStateHistory.__table__,
            Incident.__table__,
            IncidentEvent.__table__,
        ],
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP TABLE IF EXISTS incident_events"))
    bind.execute(sa.text("DROP TABLE IF EXISTS incidents"))
    bind.execute(sa.text("DROP TABLE IF EXISTS device_state_history"))
    bind.execute(sa.text("DROP TABLE IF EXISTS device_addresses"))
    bind.execute(sa.text("DROP SEQUENCE IF EXISTS incident_seq"))
    bind.execute(sa.text("ALTER TABLE devices DROP COLUMN IF EXISTS serial_number"))
    bind.execute(sa.text("ALTER TABLE devices DROP COLUMN IF EXISTS default_gateway_ip"))
    # Postgres has no DROP VALUE for enum types -- the added EventType values are
    # left in place on downgrade (harmless: nothing will emit them once this
    # revision is reverted).
