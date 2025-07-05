async def render(service, middleware, render_ctx):
    """
    Generate WebShare configuration files.
    This is called by the etc service to ensure configuration files
    are created on boot before the webshare service starts.
    """
    # Check if the service is enabled for autostart
    try:
        service_config = await middleware.call(
            'service.query',
            [['service', '=', 'webshare']],
            {'get': True}
        )
        if not service_config['enable']:
            # Service is not enabled, skip generating config files
            return None
    except Exception:
        # If we can't query the service, assume it's not enabled
        return None

    try:
        # Auto-configure pools if needed (for autostart scenario)
        # Use skip_reload=True to avoid circular dependency during
        # service startup
        await middleware.call('webshare._auto_configure_pools_if_needed', True)

        # Call the webshare service's configuration generator
        await middleware.call('webshare._generate_config_files')

        # Ensure config files are written and accessible before
        # service starts
        await middleware.run_in_thread(
            middleware.call_sync, 'webshare._ensure_config_files_exist'
        )
    except Exception as e:
        # Log the error but don't fail the etc generation
        middleware.logger.warning(
            f'Failed to generate webshare config files: {e}'
        )

    # Return None as we're handling file writing internally
    return None
