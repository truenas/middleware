<%
    import os
    import re

    users = middleware.call_sync('user.query', [['email', '!=', '']])

    with open(os.path.join('/conf/base/etc', '' if IS_LINUX else 'mail', 'aliases'), 'r') as f:
        base_data = f.read()

    write_users = []
    for user in users:
        if re.findall(fr'^{user["username"]}:', base_data, re.M):
            base_data = re.sub(fr'(^{user["username"]}:.*)', f'{user["username"]}: {user["email"]}', base_data, flags=re.M)
        else:
            write_users.append(user)
%>\
${base_data}
% for user in write_users:
${user['username']}: ${user['email']}
% endfor
