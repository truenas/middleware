def copy_function_metadata(f, nf):
    nf.__name__ = f.__name__
    nf.__doc__ = f.__doc__
    # Copy private attrs to new function so decorators can work on top of it
    # e.g. _pass_app
    for i in dir(f):
        if i.startswith('__'):
            continue
        if i.startswith('_'):
            setattr(nf, i, getattr(f, i))
    for i in ["accepts", "returns"]:
        if hasattr(f, i):
            setattr(nf, i, getattr(f, i))
