% for user in ds.query("users"):
${user['username']}:${user['unixhash']}:${user['id']}:${user['group']}::0:0:${user['full_name']}:${user['home']}:${user['shell']}
% endfor