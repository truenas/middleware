async def migrate(middleware):
    # This is required because earlier middleware was running considering openssl security level to be 1
    # but with moving to debian, the default now is 2 which enforces security standards. It means that potentially
    # user might have configured cert for system which might not comply with security level 2 and UI becoming
    # inaccessible in this regard because of that
    system_cert_id = (await middleware.call('system.general.config'))['ui_certificate']
    if not system_cert_id or await middleware.call(
        'certificate.cert_services_validation', system_cert_id, 'certificate', False
    ):
        await middleware.call('certificate.setup_self_signed_cert_for_ui')
        await (await middleware.call('service.control', 'RESTART', 'http')).wait(raise_error=True)
