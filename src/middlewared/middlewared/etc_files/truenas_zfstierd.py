from truenas_pylicensed.features import LicenseFeature
from truenas_zfstierd_common.configfile import ZFSTierdGlobalConfig, generate_config


def render(service, middleware):
    config = middleware.call_sync("zfs.tier.config")
    entitled = middleware.call_sync2(
        middleware.services.truenas.entitlements.check, LicenseFeature.ZFSTIER
    ).entitled
    if config.enabled and not entitled:
        # Gated on config.enabled so a system that never turned tiering on stays silent.
        # Raising instead of warning is not an option: a render exception is swallowed and
        # the previous file left in place -- the exact stale config this gate exists to
        # prevent.
        middleware.logger.warning(
            "ZFS tiering is enabled in configuration but this system is not entitled to the "
            "ZFSTIER feature; rendering the daemon configuration with tiering disabled."
        )
    cfg = ZFSTierdGlobalConfig(
        max_concurrent_jobs=config.max_concurrent_jobs,
        reporting_write_interval=60,
        rewrite_chunk_size=1024,
        reporting_callback_interval=1,
        max_used_percent=config.max_used_percentage,
        enabled=config.enabled and entitled,
    )
    return generate_config(cfg)
