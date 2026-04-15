async def migrate(middleware):
    # This migration earlier used to make sure that HA systems are not setting interfaces/ips
    # However we have now removed the ability for setting those attrs altogether in TNC
    # hence this migration is a no-op now
    pass
