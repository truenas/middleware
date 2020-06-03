import subprocess
import sysctl

default_sysctl = {}


def sysctl_configuration(middleware):
    tuneables = middleware.call_sync('tunable.query', [['type', '=', 'SYSCTL']])
    for tuneable in tuneables:
        value_default = None

        try:
            value_default = middleware.call_sync('tunable.get_default_value', tuneable['var'])
        except KeyError:
            pass
        if tuneable['enabled'] is True:
            if value_default is None:
                try:
                    value_default = sysctl.filter(tuneable['var'])[0].value
                    middleware.call_sync('tunable.set_default_value', tuneable['var'], value_default)
                except IndexError:
                    # Not able to set the default value
                    middleware.logger.error(
                        'Failed to get sysctl default value of %s', tuneable['var'], exc_info=True
                    )

            ret = subprocess.run(
                ['sysctl', f'{tuneable["var"]}="{tuneable["value"]}"'],
                capture_output=True
            )
            if ret.returncode:
                middleware.logger.debug(
                    'Failed to set sysctl %s -> %s: %s',
                    tuneable['var'], tuneable['value'], ret.stderr.decode(),
                )
        else:
            if value_default is not None:
                ret = subprocess.run(
                    ['sysctl', f'{tuneable["var"]}="{value_default}"'],
                    capture_output=True
                )
                if ret.returncode:
                    middleware.logger.debug(
                        'Failed to set sysctl %s -> %s: %s',
                        tuneable['var'], tuneable['value'], ret.stderr.decode(),
                    )


def render(service, middleware):
    sysctl_configuration(middleware)
