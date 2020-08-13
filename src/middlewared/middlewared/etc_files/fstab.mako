<%
	import os

	# That file is not supposed to exist anymore but lets keep backward compatibility for now
	base_path = '/conf/base/etc/fstab'
	if os.path.isfile(base_path):
		with open(base_path, 'r') as f:
			base = f.read()
	else:
		base = ''
%>\
% if base:
${base}
% endif
% if IS_LINUX:
boot-pool/grub /boot/grub	zfs	relatime,defaults	0	0
% else:
fdescfs	/dev/fd	fdescfs rw	0 0
% endif