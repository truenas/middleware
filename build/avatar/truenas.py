import os

def setup_arg_parser(parser):
    caches = {
        'build_repo_cache':'/truenas-build/git-repo/truenas.git',
        'freebsd_repo_cache':'/truenas-build/git-repo/freebsd.git',
        'ports_repo_cache':'/truenas-build/git-repo/ports.git'}
    for opt, path in caches.items():
        if os.path.isdir(path):
            parser.set_defaults(**{opt:path})
    parser.set_defaults(**{'build_repo':
        'git@gitserver.ixsystems.com:/git/repos/truenas-build/git-repo/truenas.git'})
    parser.set_defaults(**{'freebsd_repo':
        'git@gitserver.ixsystems.com:/git/repos/truenas-build/git-repo/freebsd.git'})
    parser.set_defaults(**{'ports_repo':
        'git@gitserver.ixsystems.com:/git/repos/truenas-build/git-repo/ports.git'})


