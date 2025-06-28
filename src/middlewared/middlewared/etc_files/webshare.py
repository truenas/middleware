async def render(service, middleware, render_ctx):
    """
    Generate WebShare configuration files.
    This is called by the etc service to ensure configuration files
    are created on boot before the webshare service starts.
    """
    # Call the webshare service's configuration generator
    await middleware.call('webshare._generate_config_files')

    # Return None as we're handling file writing internally
    return None
