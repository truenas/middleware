import json
import os

from middlewared.service import Service
from middlewared.utils.plugins import load_modules
from middlewared.utils.python import get_middlewared_dir


def load_migrations():
    return sorted(load_modules(
        os.path.join(get_middlewared_dir(), 'plugins/kubernetes_linux/migrations')
    ), key=lambda x: x.__name__)


class KubernetesMigrationsService(Service):

    MIGRATIONS_FILE_NAME = 'migrations.json'

    class Config:
        namespace = 'k8s.migration'
        private = True

    @property
    def migration_file_path(self):
        return os.path.join(
            '/mnt', self.middleware.call_sync('kubernetes.config')['dataset'], self.MIGRATIONS_FILE_NAME
        )

    def applied(self):
        try:
            with open(self.migration_file_path, 'r') as f:
                return json.loads(f.read())
        except FileNotFoundError:
            self.logger.error('%r migration file not found, creating one', self.migration_file_path)
        except json.JSONDecodeError:
            self.logger.error('Malformed %r migration file found, re-creating', self.migration_file_path)

        with open(self.migration_file_path, 'w') as f:
            f.write(json.dumps({
                'migrations': [],
            }))
