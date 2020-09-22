<%
    config = middleware.call_sync('datastore.query', 'services.kubernetes', [], {'get': True})
    if not middleware.call_sync('k8s.cni.validate_cni_integrity', 'kube_router'):
        middleware.logger.debug('Kube-router CNI configuration not generated due to missing credentials.')
        raise FileShouldNotExist()
    kube_router = config['cni_config']['kube_router']
%>\
apiVersion: v1
clusterCIDR: ${config["cluster_cidr"]}
kind: Config
clusters:
- name: cluster
  cluster:
    server: https://127.0.0.1:6443
    certificate-authority-data: ${kube_router['ca']}
users:
- name: kube-router
  user:
    token: ${kube_router['token']}
contexts:
- name: kube-router-context
  context:
    cluster: cluster
    user: kube-router
current-context: kube-router-context