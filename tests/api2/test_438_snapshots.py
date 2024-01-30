#!/usr/bin/env python3
import os
import pytest
import sys

from middlewared.test.integration.assets.pool import dataset, snapshot

apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import hostname, ip, pool_name
from functions import DELETE, GET, POST, PUT, wait_on_job

pytestmark = pytest.mark.zfs


def _verify_snapshot_keys_present(snap, expected, unexpected):
    """
    Verify that the snapshot returned by the query has the expected keys in its dict
    and none of the unexpected ones.

    :param snap: a dict containing snapshot data
    :param expected: a list of strings, expected key names in the dict
    :param unexpected: a list of strings, key names that should not be in the dict
    """
    assert set(expected).issubset(set(snap.keys())), f"Failed to get all expected keys: {snap.keys()}"
    for key in unexpected:
        assert key not in snap.keys(), f"Unexpectedly, was returned '{key}'"


def _verify_snapshot_against_config(snap, dataset_id, snap_config):
    """
    Verify that the snapshot returned by the query has data that matches the data
    returned then the dataset and snapshot were created.

    :param snap: a dict containing snapshot data
    :param dataset_id: dataset name
    :param snap_config: a dict containing the snapshot data (when it was created)
    """
    assert snap['pool'] == dataset_id.split('/')[0], f"Incorrect pool: {snap}"
    assert snap['name'] == snap_config['name'], f"Incorrect name: {snap}"
    assert snap['type'] == "SNAPSHOT", f"Incorrect type: {snap}"
    assert snap['snapshot_name'] == snap_config['snapshot_name'], f"Incorrect snapshot_name: {snap}"
    assert snap['dataset'] == dataset_id, f"Incorrect dataset: {snap}"
    assert snap['id'] == snap_config['id'], f"Incorrect id: {snap}"
    assert isinstance(snap['createtxg'], str), f"Incorrect type for createtxg: {snap}"
    assert snap['createtxg'] == snap_config['createtxg'], f"Incorrect createtxg: {snap}"


def _verify_snapshot_properties(snap, properties_list):
    """
    Verify that the snapshot returned by the query has the expected items in its
    'properties' value.

    In the case of 'name' and 'createtxg' properties we perform additional checks
    as this data should be present twice in snap.

    :param snap: a dict containing snapshot data
    :param properties_list: a list of strings, key names of properties that should
    be present in snap['properties']
    """
    for prop in properties_list:
        assert prop in snap['properties'], f"Missing property: {prop}"
    # Special checking if name requested
    if 'name' in properties_list:
        assert snap['properties']['name']['value'] == snap['name'], f"Name property does not match {snap['properties']['name']}"
    if 'createtxg' in properties_list:
        assert snap['properties']['createtxg']['value'] == snap['createtxg'], f"createtxg property does not match {snap['properties']['name']}"

#
# Snapshot query: filter by dataset name
#

def _test_xxx_snapshot_query_filter_dataset(dataset_name, properties_list,
        expected_keys = ['pool', 'name', 'type', 'snapshot_name', 'dataset', 'id', 'createtxg'],
        unexpected_keys = ['properties']):
    """
    Perform snapshot queries, filtered by dataset name.

    :param dataset_name: a string, the name of the dataset to be created and used in queries.
    :param properties_list: a list of strings, the names to be queried in snapshot properties option
    :expected_keys: a list of strings, the key names expected to be present in the snapshot dict
    :unexpected_keys: a list of strings, the key names expected NOT to be present in the snapshot dict
    """
    with dataset(dataset_name) as dataset_id:
        with snapshot(dataset_id, "snap01", get=True) as snap01_config:
            payload = {
                'query-filters': [['dataset', '=', dataset_id]],
                'query-options': {
                    'extra': {
                        'properties': properties_list
                    }
                }
            }
            results = GET(f"/zfs/snapshot", payload)
            assert results.status_code == 200, results.text
            assert isinstance(results.json(), list), results.text
            snaps = results.json()
            # Check that we have one snap returned and that it has the expected
            # data
            assert len(snaps) == 1, snaps
            snap = snaps[0]
            _verify_snapshot_keys_present(snap, expected_keys, unexpected_keys)
            _verify_snapshot_against_config(snap, dataset_id, snap01_config)
            if 'properties' not in unexpected_keys:
                _verify_snapshot_properties(snap, properties_list)

            # Now create another snapshot and re-issue the query to check the
            # new results.
            with snapshot(dataset_id, "snap02", get=True) as snap02_config:
                results = GET(f"/zfs/snapshot", payload)
                assert results.status_code == 200, results.text
                assert isinstance(results.json(), list), results.text
                snaps = results.json()
                # Check that we have two snaps returned and that they have the expected
                # data.
                assert len(snaps) == 2, snaps

                # Need to sort the snaps by createtxg
                ssnaps = sorted(snaps, key=lambda d: int(d['createtxg']))
                snap01 = ssnaps[0]
                snap02 = ssnaps[1]
                _verify_snapshot_keys_present(snap01, expected_keys, unexpected_keys)
                _verify_snapshot_against_config(snap01, dataset_id, snap01_config)
                _verify_snapshot_keys_present(snap02, expected_keys, unexpected_keys)
                _verify_snapshot_against_config(snap02, dataset_id, snap02_config)
                if 'properties' not in unexpected_keys:
                    _verify_snapshot_properties(snap01, properties_list)
                    _verify_snapshot_properties(snap02, properties_list)

                existing_snaps = {snap01['createtxg'], snap02['createtxg']}

                # Now create *another* dataset and snapshot and ensure we
                # only see the snapshots we're supposed to.
                with dataset(f"{dataset_name}2") as dataset2:
                    with snapshot(dataset2, "snap03", get=True) as snap03_config:
                        # First issue the original query again & ensure we still have
                        # the expected snapshots
                        results = GET(f"/zfs/snapshot", payload)
                        assert results.status_code == 200, results.text
                        assert isinstance(results.json(), list), results.text
                        snaps = results.json()
                        assert len(snaps) == 2, snaps
                        for snap in snaps:
                            assert snap['createtxg'] in existing_snaps, f"Got unexpected snap: {snap}"

                        # Next issue the query with a different filter
                        payload.update({
                            'query-filters': [['dataset', '=', dataset2]]
                            })
                        results = GET(f"/zfs/snapshot", payload)
                        assert results.status_code == 200, results.text
                        assert isinstance(results.json(), list), results.text
                        snaps = results.json()
                        assert len(snaps) == 1, snaps
                        snap = snaps[0]
                        assert snap['createtxg'] not in existing_snaps, f"Got unexpected snap: {snap}"
                        new_snaps = {snap['createtxg']}
                        _verify_snapshot_keys_present(snap, expected_keys, unexpected_keys)
                        _verify_snapshot_against_config(snap, dataset2, snap03_config)
                        if 'properties' not in unexpected_keys:
                            _verify_snapshot_properties(snap, properties_list)

                        # Next issue the query with a bogus filter
                        payload.update({
                            'query-filters': [['dataset', '=', f"{dataset_name}-BOGUS"]]
                            })
                        results = GET(f"/zfs/snapshot", payload)
                        assert results.status_code == 200, results.text
                        assert isinstance(results.json(), list), results.text
                        snaps = results.json()
                        assert len(snaps) == 0, snaps

                        # Next issue the query WITHOUT a filter.  It's possible
                        # that this test could be run while other snapshots are
                        # present, so take that into account during checks, e.g.
                        # assert count >= 3 rather than == 3
                        payload.update({
                            'query-filters': []
                            })
                        results = GET(f"/zfs/snapshot", payload)
                        assert results.status_code == 200, results.text
                        assert isinstance(results.json(), list), results.text
                        snaps = results.json()
                        assert len(snaps) >= 3, len(snaps)
                        all_snaps = set([s['createtxg'] for s in snaps])
                        assert existing_snaps.issubset(all_snaps), "Existing snaps not returned in filterless query"
                        assert new_snaps.issubset(all_snaps), "New snaps not returned in filterless query"

                    # Let the snap03 get cleaned up, and then ensure even with a filterless query
                    # that it is no longer returned.
                    results = GET(f"/zfs/snapshot", payload)
                    assert results.status_code == 200, results.text
                    assert isinstance(results.json(), list), results.text
                    snaps = results.json()
                    assert len(snaps) >= 2, len(snaps)
                    all_snaps = set([s['createtxg'] for s in snaps])
                    assert existing_snaps.issubset(all_snaps), "Existing snaps not returned in filterless query"
                    assert not new_snaps.issubset(all_snaps), "New snaps returned in filterless query"


def _test_simple_snapshot_query_filter_dataset(dataset_name, properties_list):
    """
    Perform simple snapshot queries, filtered by dataset name.

    :param dataset_name: a string, the name of the dataset to be created and used in queries.
    :param properties_list: a list of strings, the names to be queried in snapshot properties option
    """
    _test_xxx_snapshot_query_filter_dataset(dataset_name, properties_list,
        expected_keys = ['pool', 'name', 'type', 'snapshot_name', 'dataset', 'id', 'createtxg'],
        unexpected_keys = ['properties'])


def _test_full_snapshot_query_filter_dataset(dataset_name, properties_list):
    """
    Perform non-simple (non fast-path) snapshot queries, filtered by dataset name.

    :param dataset_name: a string, the name of the dataset to be created and used in queries.
    :param properties_list: a list of strings, the names to be queried in snapshot properties option
    """
    _test_xxx_snapshot_query_filter_dataset(dataset_name, properties_list,
        ['pool', 'name', 'type', 'snapshot_name', 'dataset', 'id', 'createtxg', 'properties'],
        [])


def test_01_snapshot_query_filter_dataset_props_name(request):
    """
    Test snapshot query, filtered by dataset with properties option: 'name'

    The results should be simple (fast-path) without 'properties'.
    """
    _test_simple_snapshot_query_filter_dataset("ds-snapshot-simple-query-name", ['name'])


def test_02_snapshot_query_filter_dataset_props_createtxg(request):
    """
    Test snapshot query, filtered by dataset with properties option: 'createtxg'

    The results should be simple (fast-path) without 'properties'.
    """
    _test_simple_snapshot_query_filter_dataset("ds-snapshot-simple-query-createtxg", ['createtxg'])


def test_03_snapshot_query_filter_dataset_props_name_createtxg(request):
    """
    Test snapshot query, filtered by dataset with properties option: 'name', 'createtxg'

    The results should be simple (fast-path) without 'properties'.
    """
    _test_simple_snapshot_query_filter_dataset("ds-snapshot-simple-query-name-createtxg", ['name', 'createtxg'])
    _test_simple_snapshot_query_filter_dataset("ds-snapshot-simple-query-createtxg-name", ['createtxg', 'name'])


def test_04_snapshot_query_filter_dataset_props_used(request):
    """
    Test snapshot query, filtered by dataset including properties option: 'used'

    The results should be regular (NON fast-path) query that returns 'properties'.
    """
    _test_full_snapshot_query_filter_dataset("ds-snapshot-simple-query-createtxg", ['used'])
    _test_full_snapshot_query_filter_dataset("ds-snapshot-simple-query-createtxg", ['used', 'name'])
    _test_full_snapshot_query_filter_dataset("ds-snapshot-simple-query-createtxg", ['used', 'name', 'createtxg'])
    _test_full_snapshot_query_filter_dataset("ds-snapshot-simple-query-createtxg", ['used', 'createtxg'])


#
# Snapshot query: filter by snapshot name
#

def _test_xxx_snapshot_query_filter_snapshot(dataset_name, properties_list, expected_keys, unexpected_keys):
    """
    Perform snapshot queries, filtered by snapshot name.

    :param dataset_name: a string, the name of the dataset to be created and used in queries.
    :param properties_list: a list of strings, the names to be queried in snapshot properties option
    :expected_keys: a list of strings, the key names expected to be present in the snapshot dict
    :unexpected_keys: a list of strings, the key names expected NOT to be present in the snapshot dict
    """
    with dataset(dataset_name) as dataset_id:
        with snapshot(dataset_id, "snap01", get=True) as snap01_config:
            with snapshot(dataset_id, "snap02", get=True) as snap02_config:
                # Query snap01
                payload = {
                    'query-filters': [['name', '=', snap01_config['name']]],
                    'query-options': {
                        'extra': {
                            'properties': properties_list
                        }
                    }
                }
                results = GET(f"/zfs/snapshot", payload)
                assert results.status_code == 200, results.text
                assert isinstance(results.json(), list), results.text
                snaps = results.json()
                # Check that we have one snap returned and that it has the expected
                # data
                assert len(snaps) == 1, snaps
                snap = snaps[0]
                _verify_snapshot_keys_present(snap, expected_keys, unexpected_keys)
                _verify_snapshot_against_config(snap, dataset_id, snap01_config)
                if 'properties' not in unexpected_keys:
                    _verify_snapshot_properties(snap, properties_list)

                # Query snap02
                payload = {
                    'query-filters': [['name', '=', snap02_config['name']]],
                    'query-options': {
                        'extra': {
                            'properties': properties_list
                        }
                    }
                }
                results = GET(f"/zfs/snapshot", payload)
                assert results.status_code == 200, results.text
                assert isinstance(results.json(), list), results.text
                snaps = results.json()
                # Check that we have one snap returned and that it has the expected
                # data
                assert len(snaps) == 1, snaps
                snap = snaps[0]
                _verify_snapshot_keys_present(snap, expected_keys, unexpected_keys)
                _verify_snapshot_against_config(snap, dataset_id, snap02_config)
                if 'properties' not in unexpected_keys:
                    _verify_snapshot_properties(snap, properties_list)

            # Allow snap02 to be destroyed, then query again to make sure we don't get it
            results = GET(f"/zfs/snapshot", payload)
            assert results.status_code == 200, results.text
            assert isinstance(results.json(), list), results.text
            snaps = results.json()
            assert len(snaps) == 0, snaps


def _test_simple_snapshot_query_filter_snapshot(dataset_name, properties_list):
    """
    Perform simple snapshot queries, filtered by snapshot name.

    :param dataset_name: a string, the name of the dataset to be created and used in queries.
    :param properties_list: a list of strings, the names to be queried in snapshot properties option
    """
    _test_xxx_snapshot_query_filter_snapshot(dataset_name, properties_list,
        expected_keys = ['pool', 'name', 'type', 'snapshot_name', 'dataset', 'id', 'createtxg'],
        unexpected_keys = ['properties'])


def _test_full_snapshot_query_filter_snapshot(dataset_name, properties_list):
    """
    Perform non-simple (non fast-path) snapshot queries, filtered by snapshot name.

    :param dataset_name: a string, the name of the dataset to be created and used in queries.
    :param properties_list: a list of strings, the names to be queried in snapshot properties option
    """
    _test_xxx_snapshot_query_filter_snapshot(dataset_name, properties_list,
        ['pool', 'name', 'type', 'snapshot_name', 'dataset', 'id', 'createtxg', 'properties'],
        [])


def test_05_snapshot_query_filter_snapshot_props_name(request):
    """
    Test snapshot query, filtered by snapshot with properties option: 'name'

    The results should be simple (fast-path) without 'properties'.
    """
    _test_simple_snapshot_query_filter_snapshot("ds-snapshot-simple-query-name", ['name'])


def test_06_snapshot_query_filter_snapshot_props_createtxg(request):
    """
    Test snapshot query, filtered by snapshot with properties option: 'createtxg'

    The results should be simple (fast-path) without 'properties'.
    """
    _test_simple_snapshot_query_filter_snapshot("ds-snapshot-simple-query-createtxg", ['createtxg'])


def test_07_snapshot_query_filter_snapshot_props_name_createtxg(request):
    """
    Test snapshot query, filtered by snapshot with properties option: 'name', 'createtxg'

    The results should be simple (fast-path) without 'properties'.
    """
    _test_simple_snapshot_query_filter_snapshot("ds-snapshot-simple-query-name-createtxg", ['name', 'createtxg'])
    _test_simple_snapshot_query_filter_snapshot("ds-snapshot-simple-query-createtxg-name", ['createtxg', 'name'])


def test_08_snapshot_query_filter_snapshot_props_used(request):
    """
    Test snapshot query, filtered by snapshot including properties option: 'used'

    The results should be regular (NON fast-path) query that returns 'properties'.
    """
    _test_full_snapshot_query_filter_snapshot("ds-snapshot-simple-query-createtxg", ['used'])
    _test_full_snapshot_query_filter_snapshot("ds-snapshot-simple-query-createtxg", ['used', 'name'])
    _test_full_snapshot_query_filter_snapshot("ds-snapshot-simple-query-createtxg", ['used', 'name', 'createtxg'])
    _test_full_snapshot_query_filter_snapshot("ds-snapshot-simple-query-createtxg", ['used', 'createtxg'])


#
# Snapshot query: filter by pool name
#

def _test_xxx_snapshot_query_filter_pool(dataset_name, properties_list, expected_keys, unexpected_keys):
    """
    Perform snapshot queries, filtered by pool name.

    :param dataset_name: a string, the name of the dataset to be created and used in queries.
    :param properties_list: a list of strings, the names to be queried in snapshot properties option
    :expected_keys: a list of strings, the key names expected to be present in the snapshot dict
    :unexpected_keys: a list of strings, the key names expected NOT to be present in the snapshot dict
    """
    with dataset(dataset_name) as dataset_id:
        # Before we create any snapshots for this test, query snapshots
        payload = {
            'query-filters': [['pool', '=', pool_name]],
            'query-options': {
                'extra': {
                    'properties': properties_list
                }
            }
        }
        results = GET(f"/zfs/snapshot", payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list), results.text
        snaps = results.json()
        original_snap_count = len(snaps)

        with snapshot(dataset_id, "snap01", get=True) as snap01_config:
            with snapshot(dataset_id, "snap02", get=True) as snap02_config:
                # Query again
                results = GET(f"/zfs/snapshot", payload)
                assert results.status_code == 200, results.text
                assert isinstance(results.json(), list), results.text
                snaps = results.json()

                # Check that we have two additional snap returned and that 
                # they have the expected data
                assert len(snaps) == original_snap_count+2, snaps
                ssnaps = sorted(snaps, key=lambda d: int(d['createtxg']))
                snap01 = ssnaps[-2]
                snap02 = ssnaps[-1]
                _verify_snapshot_keys_present(snap01, expected_keys, unexpected_keys)
                _verify_snapshot_against_config(snap01, dataset_id, snap01_config)
                _verify_snapshot_keys_present(snap02, expected_keys, unexpected_keys)
                _verify_snapshot_against_config(snap02, dataset_id, snap02_config)
                if 'properties' not in unexpected_keys:
                    _verify_snapshot_properties(snap01, properties_list)
                    _verify_snapshot_properties(snap02, properties_list)

            # Allow snap02 to be destroyed & query again.
            results = GET(f"/zfs/snapshot", payload)
            assert results.status_code == 200, results.text
            assert isinstance(results.json(), list), results.text
            snaps = results.json()

            assert len(snaps) == original_snap_count+1, snaps
            ssnaps = sorted(snaps, key=lambda d: int(d['createtxg']))
            snap01 = ssnaps[-1]
            _verify_snapshot_keys_present(snap01, expected_keys, unexpected_keys)
            _verify_snapshot_against_config(snap01, dataset_id, snap01_config)
            if 'properties' not in unexpected_keys:
                _verify_snapshot_properties(snap01, properties_list)


def _test_simple_snapshot_query_filter_pool(dataset_name, properties_list):
    """
    Perform simple snapshot queries, filtered by pool name.

    :param dataset_name: a string, the name of the dataset to be created and used in queries.
    :param properties_list: a list of strings, the names to be queried in snapshot properties option
    """
    _test_xxx_snapshot_query_filter_pool(dataset_name, properties_list,
        expected_keys = ['pool', 'name', 'type', 'snapshot_name', 'dataset', 'id', 'createtxg'],
        unexpected_keys = ['properties'])


def _test_full_snapshot_query_filter_pool(dataset_name, properties_list):
    """
    Perform non-simple (non fast-path) snapshot queries, filtered by pool name.

    :param dataset_name: a string, the name of the dataset to be created and used in queries.
    :param properties_list: a list of strings, the names to be queried in snapshot properties option
    """
    _test_xxx_snapshot_query_filter_pool(dataset_name, properties_list,
        ['pool', 'name', 'type', 'snapshot_name', 'dataset', 'id', 'createtxg', 'properties'],
        [])


def test_09_snapshot_query_filter_pool_props_name(request):
    """
    Test snapshot query, filtered by pool with properties option: 'name'

    The results should be simple (fast-path) without 'properties'.
    """
    _test_simple_snapshot_query_filter_pool("ds-snapshot-simple-query-name", ['name'])


def test_10_snapshot_query_filter_pool_props_createtxg(request):
    """
    Test snapshot query, filtered by pool with properties option: 'createtxg'

    The results should be simple (fast-path) without 'properties'.
    """
    _test_simple_snapshot_query_filter_pool("ds-snapshot-simple-query-createtxg", ['createtxg'])


def test_11_snapshot_query_filter_pool_props_name_createtxg(request):
    """
    Test snapshot query, filtered by pool with properties option: 'name', 'createtxg'

    The results should be simple (fast-path) without 'properties'.
    """
    _test_simple_snapshot_query_filter_pool("ds-snapshot-simple-query-name-createtxg", ['name', 'createtxg'])
    _test_simple_snapshot_query_filter_pool("ds-snapshot-simple-query-createtxg-name", ['createtxg', 'name'])


def test_12_snapshot_query_filter_pool_props_used(request):
    """
    Test snapshot query, filtered by pool including properties option: 'used'

    The results should be regular (NON fast-path) query that returns 'properties'.
    """
    _test_full_snapshot_query_filter_pool("ds-snapshot-simple-query-createtxg", ['used'])
    _test_full_snapshot_query_filter_pool("ds-snapshot-simple-query-createtxg", ['used', 'name'])
    _test_full_snapshot_query_filter_pool("ds-snapshot-simple-query-createtxg", ['used', 'name', 'createtxg'])
    _test_full_snapshot_query_filter_pool("ds-snapshot-simple-query-createtxg", ['used', 'createtxg'])
