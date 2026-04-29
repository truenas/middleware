import uuid


async def migrate(middleware):
    await middleware.call(
        "datastore.insert",
        "system.globalid", {
            "system_uuid": str(uuid.uuid4())
        }
    )

    # Generate nfs.conf now that system.global.id exists. On first boot,
    # nfs.conf.mako raises FileShouldNotExist until this ID is created,
    # which prevents the rpc-pipefs-generator from mounting rpc_pipefs
    # (needed by nfs-idmapd). Writing nfs.conf here ensures it exists
    # before the POST_INIT daemon-reload re-runs the generator.
    await middleware.call("etc.generate", "nfsd")
