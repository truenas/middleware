% for user in middleware.call_sync('user.query', [], {'order_by': ['-builtin', 'uid']}):
<%
if user['password_disabled']:
    passwd = "*"
elif user['locked']:
    passwd = "!"
else:
    passwd = user['unixhash']
%>\
${user['username']}:${passwd}:18397:0:99999:7:::
% endfor
