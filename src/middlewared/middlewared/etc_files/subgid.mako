<%
from middlewared.api.base.types.user import INCUS_IDMAP_MIN, INCUS_IDMAP_COUNT
from middlewared.utils.filter_list import filter_list

mapped = filter_list(render_ctx['group.query'], [
    ['local', '=', True],
    ['userns_idmap', 'nin', [0, None]],
    ['roles', '=', []]
])
%>\
0:${INCUS_IDMAP_MIN}:${INCUS_IDMAP_COUNT}
% for group in mapped:
0:${group['gid']}:${group['gid'] if group['userns_idmap'] == 'DIRECT' else group['userns_idmap']}
% endfor
