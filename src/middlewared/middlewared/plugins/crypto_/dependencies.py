from middlewared.service import CallError


def check_dependencies(middleware, cert_type, id):
    if cert_type == 'CA':
        key = 'truenas_certificate_authorities'
        method = 'certificateauthority.check_dependencies'
    else:
        key = 'truenas_certificates'
        method = 'certificate.check_dependencies'

    middleware.call_sync(method, id)

    chart_releases = middleware.call_sync(
        'chart.release.query', [[f'resources.{key}', 'rin', id]], {'extra': {'retrieve_resources': True}}
    )
    if chart_releases:
        raise CallError(
            f'Certificate{" Authority" if cert_type == "CA" else ""} cannot be deleted as it is being used by '
            f'{", ".join([c["id"] for c in chart_releases])} chart release(s).'
        )
