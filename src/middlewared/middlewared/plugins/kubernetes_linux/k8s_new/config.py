import base64
import contextlib
import os
import ssl
import tempfile

from typing import Optional

from middlewared.plugins.kubernetes_linux.yaml import yaml

from .utils import KUBECONFIG_FILE


CONFIG_OBJ = None


class Config:

    def __init__(self):
        self.ca_file_path: Optional[str] = None
        self.cert_file_path: Optional[str] = None
        self.cert_key_file_path: Optional[str] = None
        self.server: Optional[str] = None
        self.ssl_context: Optional[str] = None
        self.initialize_context()

    def initialize_context(self) -> None:
        with open(KUBECONFIG_FILE, 'r') as f:
            k8s_config = yaml.safe_load(f.read())

        self.server = k8s_config['clusters'][0]['cluster']['server']

        for consumer_plural, consumer, cert_type, local_var in (
            ('users', 'user', 'client-certificate-data', 'cert_file_path'),
            ('users', 'user', 'client-key-data', 'cert_key_file_path'),
            ('clusters', 'cluster', 'certificate-authority-data', 'ca_file_path'),
        ):
            setattr(self, local_var, tempfile.mkstemp()[1])
            with open(getattr(self, local_var), 'wb') as f:
                f.write(base64.b64decode(k8s_config[consumer_plural][0][consumer][cert_type]))

        self.ssl_context = ssl.create_default_context(cafile=self.ca_file_path)
        self.ssl_context.load_cert_chain(self.cert_file_path, self.cert_key_file_path)

    def __del__(self):
        for k in filter(bool, (self.cert_file_path, self.cert_key_file_path, self.ca_file_path)):
            with contextlib.suppress(FileNotFoundError):
                os.unlink(k)


def get_config(recreate=False) -> Config:
    global CONFIG_OBJ
    CONFIG_OBJ = CONFIG_OBJ if CONFIG_OBJ and not recreate else Config()
    return CONFIG_OBJ


def reinitialize_config() -> None:
    global CONFIG_OBJ
    CONFIG_OBJ = Config()
