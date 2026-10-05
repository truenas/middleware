import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.entitlements import entitled
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.webshare import webshare_share
from middlewared.test.integration.utils import call

PASSPHRASE = 'webshare_passphrase_12345'


@pytest.fixture
def webshare_entitled():
    # Creating a share and enabling an existing one are gated by the WEBSHARE entitlement,
    # which an unlicensed test runner does not have.
    with entitled("WEBSHARE"):
        yield


@pytest.fixture
def base():
    with dataset('webshare_sharing') as ds:
        base = f'/mnt/{ds}'
        call('filesystem.mkdir', {'path': f'{base}/finance'})
        call('filesystem.mkdir', {'path': f'{base}/legal'})
        yield base


def test_nested_path_rejected_on_create(webshare_entitled, base):
    with webshare_share(base, 'dept'):
        with pytest.raises(ValidationErrors) as ve:
            call('sharing.webshare.create', {'name': 'finance', 'path': f'{base}/finance'})

        assert f"This path is already covered by the Webshare 'dept' at {base}." in str(ve.value)


def test_parent_path_rejected_on_create(webshare_entitled, base):
    with webshare_share(f'{base}/finance', 'finance'):
        with pytest.raises(ValidationErrors) as ve:
            call('sharing.webshare.create', {'name': 'dept', 'path': base})

        assert f"This path contains the Webshare 'finance' at {base}/finance." in str(ve.value)


def test_same_path_rejected_on_create(webshare_entitled, base):
    with webshare_share(base, 'dept'):
        with pytest.raises(ValidationErrors) as ve:
            call('sharing.webshare.create', {'name': 'dept_again', 'path': base})

        assert f"This path is already covered by the Webshare 'dept' at {base}." in str(ve.value)


def test_sibling_paths_allowed(webshare_entitled, base):
    with webshare_share(f'{base}/finance', 'finance') as finance:
        with webshare_share(f'{base}/legal', 'legal') as legal:
            assert finance['path'] == f'{base}/finance'
            assert legal['path'] == f'{base}/legal'


def test_nested_path_rejected_on_update(webshare_entitled, base):
    with webshare_share(f'{base}/finance', 'finance'):
        with webshare_share(f'{base}/legal', 'legal') as legal:
            with pytest.raises(ValidationErrors) as ve:
                call('sharing.webshare.update', legal['id'], {'path': f'{base}/finance'})

            assert f"This path is already covered by the Webshare 'finance' at {base}/finance." in str(ve.value)


def test_share_does_not_overlap_itself_on_update(webshare_entitled, base):
    with webshare_share(base, 'dept') as dept:
        updated = call('sharing.webshare.update', dept['id'], {'name': 'department'})

        assert updated['name'] == 'department'
        assert updated['path'] == base


def test_disabled_share_does_not_block_create(webshare_entitled, base):
    with webshare_share(base, 'dept', {'enabled': False}):
        with webshare_share(f'{base}/finance', 'finance') as finance:
            assert finance['enabled'] is True


def test_disabled_overlapping_share_cannot_be_enabled(webshare_entitled, base):
    with webshare_share(f'{base}/finance', 'finance'):
        with webshare_share(base, 'dept', {'enabled': False}) as dept:
            with pytest.raises(ValidationErrors) as ve:
                call('sharing.webshare.update', dept['id'], {'enabled': True})

            assert f"This path contains the Webshare 'finance' at {base}/finance." in str(ve.value)


def test_overlapping_share_stays_editable_while_disabled(webshare_entitled, base):
    with webshare_share(f'{base}/finance', 'finance'):
        with webshare_share(base, 'dept', {'enabled': False}) as dept:
            updated = call('sharing.webshare.update', dept['id'], {'name': 'department'})

            assert updated['name'] == 'department'


def test_duplicate_name_rejected(webshare_entitled, base):
    with webshare_share(f'{base}/finance', 'dept'):
        with pytest.raises(ValidationErrors) as ve:
            call('sharing.webshare.create', {'name': 'dept', 'path': f'{base}/legal'})

        assert 'Share with this name already exists.' in str(ve.value)


def test_locking_dataset_marks_share_locked(webshare_entitled):
    with dataset('webshare_encrypted', {
        'encryption': True,
        'inherit_encryption': False,
        'encryption_options': {'passphrase': PASSPHRASE},
    }) as ds:
        with webshare_share(f'/mnt/{ds}', 'dept') as dept:
            assert dept['locked'] is False

            call('pool.dataset.lock', ds, job=True)
            try:
                assert call('sharing.webshare.get_instance', dept['id'])['locked'] is True
            finally:
                call('pool.dataset.unlock', ds, {
                    'datasets': [{'name': ds, 'passphrase': PASSPHRASE}],
                }, job=True)

            assert call('sharing.webshare.get_instance', dept['id'])['locked'] is False


def test_create_requires_entitlement(base):
    with entitled("WEBSHARE", False):
        with pytest.raises(ValidationErrors) as ve:
            call('sharing.webshare.create', {'name': 'dept', 'path': base})

        assert 'not licensed to use' in str(ve.value)


def test_update_requires_entitlement_unless_share_is_disabled(base):
    with entitled("WEBSHARE"):
        share = call('sharing.webshare.create', {'name': 'dept', 'path': base})

    try:
        with entitled("WEBSHARE", False):
            with pytest.raises(ValidationErrors) as ve:
                call('sharing.webshare.update', share['id'], {'name': 'department'})

            assert 'not licensed to use' in str(ve.value)

            assert call('sharing.webshare.update', share['id'], {'enabled': False})['enabled'] is False
    finally:
        call('sharing.webshare.delete', share['id'])
