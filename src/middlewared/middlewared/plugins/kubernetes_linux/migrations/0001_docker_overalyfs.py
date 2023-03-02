def migrate(middleware):
    middleware.call_sync('k8s.cri.re_initialize')
