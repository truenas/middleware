<%
from middlewared.api.base.types.user import INCUS_IDMAP_MIN, INCUS_IDMAP_COUNT
from middlewared.utils import filter_list

users = filter_list(
    render_ctx['user.query'],
    [
        ['userns_idmap', 'nin', [0, None]],  # Ensure that we never map to UID 0
        ['local', '=', True],
        ['roles', '=', []]
    ],
    {'order_by': ['uid']}
)
%>\
0:${INCUS_IDMAP_MIN}:${INCUS_IDMAP_COUNT}
% for user in users:
${user['uid']}:${user['uid'] if user['userns_idmap'] == 'DIRECT' else user['userns_idmap']}:1
% endfor
