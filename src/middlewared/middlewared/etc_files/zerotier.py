import os


def configure_zerotier(middleware):
    systemdataset = middleware.call_sync('systemdataset.config')

    if not systemdataset['path']:
        return

    zerotier_path = os.path.join(systemdataset['path'], 'services', 'zerotier-one')
    zerotier_db_path = '/var/db/zerotier-one'
    if not os.path.exists(zerotier_path):
        # This is the first time zerotier directory is going to be set up
        os.makedirs(zerotier_path)

    if not os.path.islink(zerotier_db_path) or not os.path.realpath(zerotier_db_path):
        os.symlink(zerotier_path, zerotier_db_path)


def render(service, middleware):
    configure_zerotier(middleware)
