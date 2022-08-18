from subprocess import run


def render(service, middleware):
    try:
        run(['truenas-nvdimm.py'], check=True)
    except Exception as e:
        middleware.logger.error("truenas-nvdimm.py error:\n%s", e)
        raise
