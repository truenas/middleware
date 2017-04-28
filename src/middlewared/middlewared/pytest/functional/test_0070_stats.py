def test_stats_get_sources(conn):
    req = conn.rest.get('stats/get_sources')

    assert req.status_code == 200
    assert isinstance(req.json(), dict) is True


def test_stats_get_dataset_info(conn):
    sources = conn.rest.get('stats/get_sources').json()

    for source, types in sources.items():
        # test only the first type for each source
        for _type in types[:1]:
            req = conn.rest.post('stats/get_dataset_info', data=[source, _type])
            assert req.status_code == 200
            assert isinstance(req.json(), dict) is True


def test_stats_get_dataset_info(conn):
    sources = conn.rest.get('stats/get_sources').json()

    # test only the first 5 sources
    for source, types in list(sources.items())[:5]:
        # test only the first type for each source
        for _type in types[:1]:
            req = conn.rest.post('stats/get_dataset_info', data=[source, _type])
            assert req.status_code == 200
            info = req.json()
            assert isinstance(info, dict) is True

            req = conn.rest.post('stats/get_data', data=[
                [{
                    'source': source,
                    'type': _type,
                    'dataset': list(info['datasets'].keys())[0],
                }],
                {}
            ])
            assert req.status_code == 200
            assert isinstance(req.json(), dict) is True
