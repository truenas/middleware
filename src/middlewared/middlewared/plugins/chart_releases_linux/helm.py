import os
import subprocess
import tempfile
import yaml

from middlewared.plugins.kubernetes_linux.yaml import SafeDumper
from middlewared.service import CallError, private, Service

from .utils import get_namespace


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    def helm_action(self, chart_release, chart_path, config, tn_action):
        args = ['-f']
        if os.path.exists(os.path.join(chart_path, 'ix_values.yaml')):
            args.extend([os.path.join(chart_path, 'ix_values.yaml'), '-f'])

        action = tn_action if tn_action == 'install' else 'upgrade'
        if action == 'upgrade':
            # We only keep history of max 5 upgrades
            # We input 6 here because helm considers app setting modifications as upgrades as well
            # which means that if an app setting is even just modified and is not an upgrade in scale terms
            # we will essentially only be keeping 4 major upgrades revision history. With 6, we temporarily have 6
            # secrets for the app but that gets sorted out asap after the upgrade action when we sync secrets and
            # we end up with 5 revision secrets max per app
            args.insert(0, '--history-max=6')

        with tempfile.NamedTemporaryFile(mode='w+') as f:
            f.write(yaml.dump(config, Dumper=SafeDumper))
            f.flush()

            cp = subprocess.Popen(
                ['helm', action, chart_release, chart_path, '-n', get_namespace(chart_release)] + args + [f.name],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                env=dict(os.environ, KUBECONFIG='/etc/rancher/k3s/k3s.yaml'),
            )
            stderr = cp.communicate()[1]
            if cp.returncode:
                raise CallError(f'Failed to {tn_action} chart release: {stderr.decode()}')

        self.middleware.call_sync('chart.release.clear_chart_release_portal_cache', chart_release)
