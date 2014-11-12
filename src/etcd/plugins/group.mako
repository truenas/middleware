% for group in ds.query("groups"):
${group['name']}:*:${group['id']}:${",".join(group['members'])}
% endfor