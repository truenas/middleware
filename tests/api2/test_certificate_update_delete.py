import pytest

from middlewared.test.integration.assets.crypto import (
    certificate_signing_request,
    imported_certificate,
)
from middlewared.test.integration.utils import call
from truenas_api_client import ValidationErrors


def test_update_certificate_rename():
    with certificate_signing_request('rename_src') as csr:
        updated = call('certificate.update', csr['id'], {'name': 'rename_dst'}, job=True)
        assert updated['name'] == 'rename_dst', updated
        # The fixture's finally calls certificate.delete on csr['id'] which is fine
        # — id stays the same after rename.


def test_update_certificate_rename_collision():
    with imported_certificate('rename_target'):
        with certificate_signing_request('rename_other') as csr:
            with pytest.raises(ValidationErrors):
                call('certificate.update', csr['id'], {'name': 'rename_target'}, job=True)


def test_update_renew_days_rejected_for_non_acme():
    with certificate_signing_request('renew_days_target') as csr:
        with pytest.raises(ValidationErrors):
            call('certificate.update', csr['id'], {'renew_days': 5}, job=True)
