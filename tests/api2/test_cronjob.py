from middlewared.test.integration.utils import call, ssh

TESTFILE = '/mnt/cronjob_testfile'


def test_cron_job():
    try:
        id = call(
            'cronjob.create',
            {
                'user': 'root',
                'enabled': True,
                'command': f'echo "yeah" > "{TESTFILE}"',
                'schedule': {'minute': '*/1'}
            }
        )['id']
        assert call('cronjob.query', [['id', '=', id]], {"get": True})['enabled'] is True
    except Exception as e:
        assert False, f'Unexpected failure: {str(e)}'

    call('cronjob.run', id, job=True)
    assert call('filesystem.statfs', TESTFILE)['blocksize']

    results = ssh(f'rm "{TESTFILE}"', complete_response=True)
    assert results['result'] is True, results['output']

    call('cronjob.delete', id)
    assert call('cronjob.query', [['id', '=', id]]) == []
