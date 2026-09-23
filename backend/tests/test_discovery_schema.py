import pytest
from pydantic import ValidationError

from app.schemas.discovery import DiscoveryStartRequest


def test_small_cidr_is_accepted():
    req = DiscoveryStartRequest(cidr="10.10.0.0/24")
    assert req.cidr == "10.10.0.0/24"


def test_oversized_cidr_is_rejected():
    """Guards against accidentally flooding the network with a huge discovery sweep."""
    with pytest.raises(ValidationError):
        DiscoveryStartRequest(cidr="10.0.0.0/8")


def test_invalid_cidr_is_rejected():
    with pytest.raises(ValidationError):
        DiscoveryStartRequest(cidr="not-a-cidr")
