<%
    from middlewared.plugins.gluster_linux.utils import get_gluster_workdir_dataset

    try:
        ds = get_gluster_workdir_dataset()
    except FileNotFoundError:
        ds = None

    if ds is not None:
        sysdataset_path = middleware.call_sync('systemdataset.sysdataset_path', ds)
    else:
        sysdataset_path = middleware.call_sync('systemdataset.config')['path']

    if not sysdataset_path:
        middleware.logger.error("glusterd.conf: system dataset is not mounted")
        middleware.call_sync('alert.oneshot_create', 'GlusterdWorkdirUnavail', None)
        raise FileShouldNotExist()

    middleware.call_sync('alert.oneshot_delete', 'GlusterdWorkdirUnavail', None)
    work_dir = sysdataset_path + '/glusterd'
%>\

volume management
    type mgmt/glusterd
    option working-directory ${work_dir}
    option transport-type socket
    option transport.socket.keepalive-time 10
    option transport.socket.keepalive-interval 2
    option transport.socket.read-fail-log off
    option transport.socket.listen-port 24007
    option ping-timeout 0
    option event-threads 1
#   option lock-timer 180
#   option transport.address-family inet6
#   option base-port 49152
    option max-port  60999
end-volume
