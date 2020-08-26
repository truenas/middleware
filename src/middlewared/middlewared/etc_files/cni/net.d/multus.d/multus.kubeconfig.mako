<%
    config = middleware.call_sync('kubernetes.config')
    if not all(k in (config['cni_config'].get('multus') or {}) for k in ('ca', 'token')):
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