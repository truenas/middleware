import subprocess


def test_truenas_verify():
    completed = subprocess.run('truenas_verify', timeout=30)

    # Jenkins vms alter the system files for setup, so truenas_verify should generate errors.
    assert completed.returncode != 0
    with open('/var/log/truenas_verify.log') as f:
        assert f.readline(), 'Test environment should log file verification errors.'
