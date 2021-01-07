<%
	import os

	# That file is not supposed to exist anymore but lets keep backward compatibility for now
	base_path = '/conf/base/etc/fstab'
	if os.path.isfile(base_path):
		with open(base_path, 'r') as f:
			base = f.read()
	else:
		base = ''

	boot_pool_name = middleware.call_sync('boot.pool_name')
%>\
% if base:
${base}
% endif
% if IS_LINUX:
${boot_pool_name}/grub	/boot/grub	zfs	relatime,defaults	0	0
tmpfs	/run/lock	tmpfs	rw,nosuid,nodev,noexec,relatime,size=100m	0	0
% else:
fdescfs	/dev/fd	fdescfs	rw	0 0
% endif
