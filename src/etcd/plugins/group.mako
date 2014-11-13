% for group in ds.query("groups"):
${group['name']}:*:${group['id']}:${",".join(group['members']) if 'members' in group else ""}
% endfor