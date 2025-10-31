<%
from middlewared.api.base.types.user import INCUS_IDMAP_MIN, INCUS_IDMAP_COUNT
from middlewared.utils.filter_list import filter_list

mapped = filter_list(render_ctx['user.query'], [
    ['local', '=', True],
    ['userns_idmap', 'nin', [0, None]],
    ['roles', '=', []]
])
%>\
0:${INCUS_IDMAP_MIN}:${INCUS_IDMAP_COUNT}
% for user in mapped:
0:${user['uid']}:${user['uid'] if user['userns_idmap'] == 'DIRECT' else user['userns_idmap']}
% endfor
