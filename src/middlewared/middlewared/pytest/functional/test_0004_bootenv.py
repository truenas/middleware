def test_bootenv_query(conn):
    req = conn.rest.get('bootenv')
    assert req.status_code == 200
    bes = req.json()
    assert isinstance(bes, list) is True


def test_bootenv_keep(conn):
    req = conn.rest.get('bootenv')
    be = req.json()[0]

    keep = be['keep']

    req = conn.rest.post(f'bootenv/id/{be["id"]}/set_attribute', data=[{
        'keep': not keep,
    }])
    assert req.status_code == 200
    assert isinstance(req.json(), bool) is True

    # Return to previous state
    req = conn.rest.post(f'bootenv/id/{be["id"]}/set_attribute', data=[{
        'keep': keep,
    }])
    assert req.status_code == 200
    assert isinstance(req.json(), bool) is True


def test_bootenv_activate(conn):
    req = conn.rest.get('bootenv')
    bes = req.json()

    if len(bes) == 1:
        return

    to_activate = None
    activated = None
    for be in bes:
        if 'N' not in be['active'] and 'R' not in be['active']:
            to_activate = be
        if 'N' in be['active']:
            activated = be

    if to_activate:
        req = conn.rest.post(f'bootenv/id/{to_activate["id"]}/activate')
        assert req.status_code == 200
        assert isinstance(req.json(), bool) is True

        req = conn.rest.post(f'bootenv/id/{activated["id"]}/activate')
        assert req.status_code == 200
        assert isinstance(req.json(), bool) is True


def test_bootenv_rename(conn):
    req = conn.rest.get('bootenv')
    bes = req.json()

    if len(bes) == 1:
        return

    to_rename = None
    for be in bes:
        if 'N' not in be['active']:
            to_rename = be
            break

    if to_rename:
        req = conn.rest.post(f'bootenv/id/{to_rename["id"]}/rename', data=['rename_test'])
        assert req.status_code == 200
        assert isinstance(req.json(), bool) is True

        req = conn.rest.post(f'bootenv/id/rename_test/rename', data=[to_rename['id']])
        assert req.status_code == 200
        assert isinstance(req.json(), bool) is True
