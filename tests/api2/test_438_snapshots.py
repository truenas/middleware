#!/usr/bin/env python3
import os
import sys
import time
from datetime import datetime

import pytest

# from middlewared.test.integration.assets.pool import dataset
from assets.REST.pool import dataset
from assets.REST.snapshot import snapshot

apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import dev_test, hostname, ip, pool_name
from functions import DELETE, GET, POST, PUT, wait_on_job
from pytest_dependency import depends

# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')


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

def _verify_snapshot_against_config(snap, dataset_config, snap_config):
    """
    Verify that the snapshot returned by the query has data that matches the data
    returned then the dataset and snapshot were created.

    :param snap: a dict containing snapshot data
    :param dataset_config: a dict containing the dataset data
    :param snap_config: a dict containing the snapshot data (when it was created)
    """
    assert snap['pool'] == dataset_config['pool'], f"Incorrect pool: {snap}"
    assert snap['name'] == snap_config['name'], f"Incorrect name: {snap}"
    assert snap['type'] == "SNAPSHOT", f"Incorrect type: {snap}"
    assert snap['snapshot_name'] == snap_config['snapshot_name'], f"Incorrect snapshot_name: {snap}"
    assert snap['dataset'] == dataset_config['name'], f"Incorrect dataset: {snap}"
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

def _test_simple_snapshot_query_filter_dataset(dataset_name, properties_list,
        expected_keys = ['pool', 'name', 'type', 'snapshot_name', 'dataset', 'id', 'createtxg'],
        unexpected_keys = ['properties']):
    """
    Perform snapshot queries, filtered by dataset name.

    As written the function is expected to yield a simple (AKA fast-path) query.  This can be
    overridden by supplying suitable values for properties_list, expected_keys and
    unexpected_keys

    :param dataset_name: a string, the name of the dataset to be created and used in queries.
    :param properties_list: a list of strings, the names to be queried in snapshot properties option
    :expected_keys: a list of strings, the key names expected to be present in the snapshot dict
    :unexpected_keys: a list of strings, the key names expected NOT to be present in the snapshot dict
    """
    with dataset(pool_name, dataset_name) as dataset_config:
        dataset_id = dataset_config['id']
        with snapshot(dataset_id, "snap01") as snap01_config:
            payload = {
                'query-filters': [['dataset', '=', dataset_config['name']]],
                'query-options': {
                    'extra': {
                        'properties': properties_list
                    }
                }
            }
            results = GET(f"/zfs/snapshot", payload)
            assert results.status_code == 200, result.text
            assert isinstance(results.json(), list), results.text
            snaps = results.json()
            # Check that we have one snap returned and that it has the expected
            # data
            assert len(snaps) == 1, snaps
            snap = snaps[0]
            _verify_snapshot_keys_present(snap, expected_keys, unexpected_keys)
            _verify_snapshot_against_config(snap, dataset_config, snap01_config)
            if 'properties' not in unexpected_keys:
                _verify_snapshot_properties(snap, properties_list)

            # Now create another snapshot and re-issue the query to check the
            # new results.
            with snapshot(dataset_id, "snap02") as snap02_config:
                results = GET(f"/zfs/snapshot", payload)
                assert results.status_code == 200, result.text
                assert isinstance(results.json(), list), results.text
                snaps = results.json()
                # Check that we have two snaps returned and that they have the expected
                # data.
                assert len(snaps) == 2, snaps

                # Need to sort the snaps by createtxg
                ssnaps = sorted(snaps, key=lambda d: int(d['createtxg']))
                snap01 = ssnaps[0]
                snap02 = ssnaps[1]
                # assert False, snap01
                # assert False, snap02
                _verify_snapshot_keys_present(snap01, expected_keys, unexpected_keys)
                _verify_snapshot_against_config(snap01, dataset_config, snap01_config)
                _verify_snapshot_keys_present(snap02, expected_keys, unexpected_keys)
                _verify_snapshot_against_config(snap02, dataset_config, snap02_config)
                if 'properties' not in unexpected_keys:
                    _verify_snapshot_properties(snap01, properties_list)
                    _verify_snapshot_properties(snap02, properties_list)

                existing_snaps = set([snap01['createtxg'], snap02['createtxg']])

                # Now create *another* dataset and snapshot and ensure we
                # only see the snapshots we're supposed to.
                with dataset(pool_name, f"{dataset_name}2") as dataset2_config:
                    with snapshot(dataset2_config['id'], "snap03") as snap03_config:
                        # First issue the original query again & ensure we still have
                        # the expected snapshots
                        results = GET(f"/zfs/snapshot", payload)
                        assert results.status_code == 200, result.text
                        assert isinstance(results.json(), list), results.text
                        snaps = results.json()
                        assert len(snaps) == 2, snaps
                        for snap in snaps:
                            assert snap['createtxg'] in existing_snaps, f"Got unexpected snap: {snap}"

                        # Next issue the query with a different filter
                        payload.update({
                            'query-filters': [['dataset', '=', dataset2_config['name']]]
                            })
                        results = GET(f"/zfs/snapshot", payload)
                        assert results.status_code == 200, result.text
                        assert isinstance(results.json(), list), results.text
                        snaps = results.json()
                        assert len(snaps) == 1, snaps
                        snap = snaps[0]
                        assert snap['createtxg'] not in existing_snaps, f"Got unexpected snap: {snap}"
                        new_snaps = set([snap['createtxg']])
                        _verify_snapshot_keys_present(snap, expected_keys, unexpected_keys)
                        _verify_snapshot_against_config(snap, dataset2_config, snap03_config)

                        # Next issue the query with a bogus filter
                        payload.update({
                            'query-filters': [['dataset', '=', f"{dataset_name}-BOGUS"]]
                            })
                        results = GET(f"/zfs/snapshot", payload)
                        assert results.status_code == 200, result.text
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
                        assert results.status_code == 200, result.text
                        assert isinstance(results.json(), list), results.text
                        snaps = results.json()
                        assert len(snaps) >= 3, len(snaps)
                        all_snaps = set([s['createtxg'] for s in snaps])
                        assert existing_snaps.issubset(all_snaps), "Existing snaps not returned in filterless query"
                        assert new_snaps.issubset(all_snaps), "New snaps not returned in filterless query"

                    # Let the snap03 get cleaned up, and then ensure even with a filterless query
                    # that it is no longer returned.
                    results = GET(f"/zfs/snapshot", payload)
                    assert results.status_code == 200, result.text
                    assert isinstance(results.json(), list), results.text
                    snaps = results.json()
                    assert len(snaps) >= 2, len(snaps)
                    all_snaps = set([s['createtxg'] for s in snaps])
                    assert existing_snaps.issubset(all_snaps), "Existing snaps not returned in filterless query"
                    assert not new_snaps.issubset(all_snaps), "New snaps returned in filterless query"

def _test_snapshot_query_filter_dataset(dataset_name, properties_list):
    """
    Perform snapshot queries, filtered by dataset name.

    :param dataset_name: a string, the name of the dataset to be created and used in queries.
    :param properties_list: a list of strings, the names to be queried in snapshot properties option
    """
    _test_simple_snapshot_query_filter_dataset(dataset_name, properties_list,
        ['pool', 'name', 'type', 'snapshot_name', 'dataset', 'id', 'createtxg', 'properties'],
        [])

def test_01_snapshot_query_filter_dataset_props_name(request):
    """
    Test snapshot query, filtered by dataset with properties option: 'name'

    The results should be simple (fast-path) without 'properties'.
    """
    depends(request, ["pool_04"], scope="session")
    _test_simple_snapshot_query_filter_dataset("ds-snapshot-simple-query-name", ['name'])

def test_02_snapshot_query_filter_dataset_props_createtxg(request):
    """
    Test snapshot query, filtered by dataset with properties option: 'createtxg'

    The results should be simple (fast-path) without 'properties'.
    """
    depends(request, ["pool_04"], scope="session")
    _test_simple_snapshot_query_filter_dataset("ds-snapshot-simple-query-createtxg", ['createtxg'])

def test_03_snapshot_query_filter_dataset_props_name_createtxg(request):
    """
    Test snapshot query, filtered by dataset with properties option: 'name', 'createtxg'

    The results should be simple (fast-path) without 'properties'.
    """
    depends(request, ["pool_04"], scope="session")
    _test_simple_snapshot_query_filter_dataset("ds-snapshot-simple-query-name-createtxg", ['name', 'createtxg'])
    _test_simple_snapshot_query_filter_dataset("ds-snapshot-simple-query-createtxg-name", ['createtxg', 'name'])

def test_04_snapshot_query_filter_dataset_props_used(request):
    """
    Test snapshot query, filtered by dataset including properties option: 'used'

    The results should be regular (NON fast-path) query that returns 'properties'.
    """
    depends(request, ["pool_04"], scope="session")
    _test_snapshot_query_filter_dataset("ds-snapshot-simple-query-createtxg", ['used'])
    _test_snapshot_query_filter_dataset("ds-snapshot-simple-query-createtxg", ['used', 'name'])
    _test_snapshot_query_filter_dataset("ds-snapshot-simple-query-createtxg", ['used', 'name', 'createtxg'])
    _test_snapshot_query_filter_dataset("ds-snapshot-simple-query-createtxg", ['used', 'createtxg'])
