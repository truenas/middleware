from middlewared.test.integration.utils import call


def test_country_choices_returns_iso_codes():
    result = call('certificate.country_choices')
    assert isinstance(result, dict)
    assert 'US' in result
    # Sanity: the ISO 3166 list has well over a hundred entries.
    assert len(result) > 100


def test_ec_curve_choices_keys():
    result = call('certificate.ec_curve_choices')
    assert set(result.keys()) == {'SECP256R1', 'SECP384R1', 'SECP521R1', 'ed25519'}


def test_acme_server_choices_includes_letsencrypt():
    result = call('certificate.acme_server_choices')
    assert isinstance(result, dict)
    assert any('letsencrypt' in uri.lower() for uri in result)


def test_extended_key_usage_choices_includes_serverauth():
    result = call('certificate.extended_key_usage_choices')
    assert 'SERVER_AUTH' in result
