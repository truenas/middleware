<%
    config = middleware.call_sync('datastore.query', 'services.kubernetes', [], {'get': True})
    if not middleware.call_sync('k8s.cni.validate_cni_integrity', 'multus'):
        middleware.logger.debug('Multus CNI configuration not generated due to missing credentials.')
        raise FileShouldNotExist()
    multus = config['cni_config']['multus']
%>\
apiVersion: v1
kind: Config
clusters:
- name: local
  cluster:
    server: https://127.0.0.1:6443
    certificate-authority-data: ${multus['ca']}
users:
- name: multus
  user:
    token: "${multus['token']}"
contexts:
- name: multus-context
  context:
    cluster: local
    user: multus
current-context: multus-context