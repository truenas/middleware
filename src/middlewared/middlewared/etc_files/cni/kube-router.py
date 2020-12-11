import json
import os


def render(service, middleware):
    if not middleware.call_sync('k8s.cni.validate_cni_integrity', 'kube_router'):
        return

    os.makedirs('/etc/cni/net.d/kube-router.d', exist_ok=True)
    with open('/etc/cni/net.d/10-kuberouter.conflist', 'w') as f:
        f.write(json.dumps(middleware.call_sync('k8s.cni.kube_router_config')))
