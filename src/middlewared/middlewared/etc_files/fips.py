import subprocess


def render(service, middleware):
    try:
        subprocess.run(['configure_fips'], capture_output=True, check=True)
    except subprocess.CalledProcessError as e:
        middleware.logger.error('configure_fips error:\n%s', e.stderr)
        raise
