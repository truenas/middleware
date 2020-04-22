def validate_gluster_jobs(self, verrors, job):
    """
    Gluster CLI operations need to run synchronously.
    """

    peer_job = self.middleware.call_sync(
        'core.get_jobs', [
            ['method', '^', 'gluster.peer'],
            ['state', '=', ['RUNNING']],
            ['id', '!=', job.id]
        ]
    )

    if peer_job:
        verrors.add(
            'validate_gluster_jobs',
            'There is an ongoing gluster peer operation. '
            'Please wait for it to complete and then try again.'
        )
        raise verrors

    volume_job = self.middleware.call_sync(
        'core.get_jobs', [
            ['method', '^', 'gluster.volume'],
            ['state', '=', ['RUNNING']],
            ['id', '!=', job.id]
        ]
    )

    if volume_job:
        verrors.add(
            'validate_gluster_jobs',
            'There is an ongoing gluster volume operation. '
            'Please wait for it to complete and then try again.'
        )
        raise verrors
