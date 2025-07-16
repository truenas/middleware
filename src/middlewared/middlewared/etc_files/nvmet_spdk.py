from middlewared.utils.nvmet.spdk import write_config
from middlewared.plugins.nvmet.constants import NAMESPACE_DEVICE_TYPE


def render(service, middleware, render_ctx):
    if middleware.call_sync('nvmet.spdk.nvmf_ready', True):

        # If we have any namespaces that are configured which are FILE
        # type, then we need to work out the blocksize for each one.
        # This will be the recordsize of the underlying dataset.
        fns = {ns['device_path'] for ns in filter(lambda ns: ns.get('device_type') == NAMESPACE_DEVICE_TYPE.FILE.api,
                                                  render_ctx['nvmet.namespace.query'])}
        if fns:
            record_sizes = {f'{item["mountpoint"]}/': int(item['recordsize']['rawvalue']) for item in
                            middleware.call_sync('pool.dataset.query',
                                                 [["mountpoint", "!=", None]],
                                                 {"select": ["name",
                                                             "children",
                                                             "mountpoint",
                                                             "recordsize.rawvalue"]})}
            path_to_recordsize = {}
            for path in fns:
                longest_match = 0
                matched_value = None
                for key, value in record_sizes.items():
                    if path.startswith(key):
                        if (length := len(key)) > longest_match:
                            longest_match = length
                            matched_value = value
                if matched_value:
                    path_to_recordsize[path] = matched_value
            # Inject into context
            render_ctx['path_to_recordsize'] = path_to_recordsize

        write_config(render_ctx)
