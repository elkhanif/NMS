import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nms_common.config import get_settings
from nms_common.crypto import CredentialCipher
from nms_common.models import DeviceCredential

_cipher = CredentialCipher(get_settings().credential_encryption_key)


async def upsert_credential(
    db: AsyncSession, device_id: uuid.UUID, credential_type, payload: dict
) -> DeviceCredential:
    result = await db.execute(
        select(DeviceCredential).where(
            DeviceCredential.device_id == device_id,
            DeviceCredential.credential_type == credential_type,
        )
    )
    credential = result.scalar_one_or_none()
    encrypted = _cipher.encrypt_json(payload)

    if credential is None:
        credential = DeviceCredential(
            device_id=device_id, credential_type=credential_type, encrypted_payload=encrypted
        )
        db.add(credential)
    else:
        credential.encrypted_payload = encrypted

    await db.flush()
    return credential


def decrypt_credential(credential: DeviceCredential) -> dict:
    """Only ever called from the monitoring worker -- never from API response paths."""
    return _cipher.decrypt_json(credential.encrypted_payload)
