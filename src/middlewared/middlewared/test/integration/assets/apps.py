import contextlib

from middlewared.test.integration.utils import call, ssh


@contextlib.contextmanager
def app(app_name: str, create_payload: dict, delete_payload: dict | None = None, options: dict | None = None):
    create_payload = create_payload | {'app_name': app_name}
    app_info = call('app.create', create_payload, options or {}, job=True)
    try:
        yield app_info
    finally:
        call('app.delete', app_name, delete_payload or {}, job=True)


def rewind_installed_version(app_name: str) -> str:
    """Pretend the app is one patch version behind, so that an upgrade is available and a rollback has a target.
    The catalog carries one version per app, so a test cannot install an older one. The preceding patch has to lie
    above the `max_version` of every config migration the app ships, or the upgrade runs them on a current config."""
    current = call('app.get_instance', app_name)['version']
    major, minor, patch = map(int, current.split('.'))
    assert patch > 0, f'{current} has no preceding patch version'
    rewound = f'{major}.{minor}.{patch - 1}'
    config_dir = f'/mnt/.ix-apps/app_configs/{app_name}'
    for path in (f'{config_dir}/versions/{current}/app.yaml', f'{config_dir}/metadata.yaml'):
        # The app's own dumper, so that the files keep the quoting that protects their strings
        ssh(
            'python3 -c "import sys, yaml; from middlewared.plugins.apps.ix_apps.utils import dump_yaml; '
            'path, version = sys.argv[1:]; data = yaml.safe_load(open(path)); '
            "data['version'] = version; data.get('metadata', {})['version'] = version; "
            f"open(path, 'w').write(dump_yaml(data))\" {path} {rewound}"
        )
    ssh(f'rm -rf {config_dir}/versions/{rewound} && mv {config_dir}/versions/{current} {config_dir}/versions/{rewound}')
    call('app.metadata_generate', job=True)
    app_info = call('app.get_instance', app_name)
    assert app_info['version'] == rewound and app_info['upgrade_available'] is True, app_info
    return rewound
