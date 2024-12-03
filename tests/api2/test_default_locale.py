from middlewared.test.integration.utils import call


def test_default_locale_exists():
    # it's important we keep this empty file
    # since it causes error like these if its missing
    # root@truenas[~]# tail -1 /var/log/error
    #   Nov 20 21:17:01 truenas CRON[399613]: pam_env(cron:session): \
    #   Unable to open env file: /etc/default/locale: No such file or directory
    rv = call("filesystem.stat", "/etc/default/locale")
    assert rv, rv
