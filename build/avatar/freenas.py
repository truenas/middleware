import os

def setup_arg_parser(parser):
    caches = {
        'build_repo_cache':'/freenas-build/freenas.git',
        'freebsd_repo_cache':'/freenas-build/trueos.git',
        'ports_repo_cache':'/freenas-build/ports.git'}
    for opt, path in caches.items():
        if os.path.isdir(path):
            parser.set_defaults(**{opt:path})
        else:
            print "No cache for missing cache for %s -> %s" % (opt, path)
    parser.set_defaults(**{'build_repo':
        'https://github.com/freenas/freenas'})
    parser.set_defaults(**{'freebsd_repo':
        'https://github.com/trueos/trueos'})
    parser.set_defaults(**{'ports_repo':
        'https://github.com/freenas/ports'})


