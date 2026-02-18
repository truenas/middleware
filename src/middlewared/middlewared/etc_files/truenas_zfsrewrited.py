from truenas_zfsrewrited_common.configfile import ZFSRewritedGlobalConfig, generate_config


def render(service, middleware):
    config = middleware.call_sync('zfs.tier.config')
    cfg = ZFSRewritedGlobalConfig(
        max_concurrent_jobs=config['max_concurrent_jobs'],
        reporting_write_interval=60,
        rewrite_chunk_size=1024,
        reporting_callback_interval=100,
        max_used_percent=80,
    )
    return generate_config(cfg)
