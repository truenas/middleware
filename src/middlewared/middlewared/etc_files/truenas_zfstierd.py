from truenas_zfstierd_common.configfile import ZFSTierdGlobalConfig, generate_config


def render(service, middleware):
    config = middleware.call_sync("zfs.tier.config")
    cfg = ZFSTierdGlobalConfig(
        max_concurrent_jobs=config["max_concurrent_jobs"],
        min_available_space=config["min_available_space"],
        reporting_write_interval=60,
        rewrite_chunk_size=1024,
        reporting_callback_interval=1,
        max_used_percent=80,
    )
    return generate_config(cfg)
