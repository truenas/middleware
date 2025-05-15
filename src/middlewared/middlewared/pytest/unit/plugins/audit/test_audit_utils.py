import pytest

from middlewared.plugins.audit.utils import (
    AUDITED_SERVICES,
    parse_query_filters,
    requires_python_filtering,
    SQL_SAFE_FIELDS,
)

def test_service_filter_equal():
    services = [s[0] for s in AUDITED_SERVICES]
    to_check, filters = parse_query_filters(services, [['service', '=', 'SMB']], True)
    assert len(to_check) == 1
    assert to_check == {'SMB'}


def test_service_filter_in():
    services = [s[0] for s in AUDITED_SERVICES]
    to_check, filters = parse_query_filters(services, [['service', 'in', ['SMB']]], True)
    assert len(to_check) == 1
    assert to_check == {'SMB'}


def test_service_filter_not_equal():
    """ Test that direct match properly excludes service """
    services = [s[0] for s in AUDITED_SERVICES]
    to_check, filters = parse_query_filters(services, [['service', '!=', 'SMB']], True)

    assert len(to_check) == len(services) - 1
    assert 'SMB' not in to_check


def test_service_filter_not_in():
    """ Test that not-in filter properly excludes service """
    services = [s[0] for s in AUDITED_SERVICES]
    to_check, filters = parse_query_filters(services, [['service', 'nin', ['SMB']]], True)

    assert len(to_check) == len(services) - 1
    assert 'SMB' not in to_check


def test_no_services():
    """ Test that all services being excluded results in empty `to_check` """
    services = [s[0] for s in AUDITED_SERVICES]
    to_check, filters = parse_query_filters(services, [['service', 'nin', services]], True)
    assert len(to_check) == 0


def test_query_filters_supported():
    """ Test that large filters containing only supported keys will get passed to SQL """
    services = [s[0] for s in AUDITED_SERVICES]
    filters = [[key, "=", services] for key in SQL_SAFE_FIELDS]
    to_check, filters_out = parse_query_filters(services, filters, False)

    assert len(to_check) == len(services)
    assert len(filters_out) == len(filters)


def test_query_filters_disjunction():
    """ Test that filters involing disjunction won't be passed to SQL """
    services = [s[0] for s in AUDITED_SERVICES]
    bad_filter = ['OR', ['username', '=', 'Bob'], ['username', '=', 'mary']]
    good_filter = ['event', '=', 'CONNECT']
    to_check, filters_out = parse_query_filters(services, [bad_filter, good_filter], False)

    # verify OR is excluded
    assert len(filters_out) == 1
    assert filters_out == [good_filter]


def test_query_filters_json():
    """ Test that excluded fields won't be passed to SQL """
    services = [s[0] for s in AUDITED_SERVICES]
    bad_filter = ['event_data', '=', {'result': 'canary'}]
    good_filter = ['event', '=', 'CONNECT']
    to_check, filters_out = parse_query_filters(services, [bad_filter, good_filter], False)

    assert len(filters_out) == 1
    assert filters_out == [good_filter]


def test_requires_python_filtering_filter_mismatch():
    """ test that mismatch between filtersets results in rejection """
    services = [s[0] for s in AUDITED_SERVICES]
    result = requires_python_filtering(services, [['event_data.result', '=', 'canary']], [], {})
    assert result is True


def test_requires_python_filtering_select_subkey():
    """ test that selecting for subkey in JSON object results in rejection """
    services = [s[0] for s in AUDITED_SERVICES]
    result = requires_python_filtering(services, [], [], {'select': ['event_data.result']})
    assert result is True


@pytest.mark.parametrize('services,options,expected', [
    ([s[0] for s in AUDITED_SERVICES], {'offset': 1}, True),
    ([s[0] for s in AUDITED_SERVICES], {'limit': 1}, True),
    (['SMB'], {'offset': 1}, False),
    (['SMB'], {'limit': 1}, False),
])
def test_requires_python_filtering_options(services, options, expected):
    """ test that selecting for subkey in JSON object results in rejection """
    result = requires_python_filtering(services, [], [], options)
    assert result is expected
