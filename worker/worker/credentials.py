from nms_common.config import get_settings
from nms_common.crypto import CredentialCipher
from nms_common.models import DeviceCredential

_cipher = CredentialCipher(get_settings().credential_encryption_key)


def decrypt_credential(credential: DeviceCredential) -> dict:
    return _cipher.decrypt_json(credential.encrypted_payload)
