% for user in ds.query("users"):
${user.name}:*:${user.id}:${user.group}:${user.full_name}:${user.home}:${user.shell}
% endfor