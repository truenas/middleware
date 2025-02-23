<%
from middlewared.api.base.types.user import INCUS_IDMAP_MIN, INCUS_IDMAP_COUNT
from middlewared.utils import filter_list

groups = filter_list(
    render_ctx['group.query'],
    [
        ['userns_idmap', 'nin', [0, None]],  # Never map GID 0
        ['local', '=', True],
        ['roles', '=', []]
    ],
    {'order_by': ['uid']}
)
%>\
0:${INCUS_IDMAP_MIN}:${INCUS_IDMAP_COUNT}
% for group in groups:
${group['gid']}:${group['gid'] if group['userns_idmap'] == 'DIRECT' else group['userns_idmap']}:1
% endfor
