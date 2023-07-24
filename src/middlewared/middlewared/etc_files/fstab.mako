<%
	boot_pool_name = middleware.call_sync('boot.pool_name')
%>\
${boot_pool_name}/grub	/boot/grub	zfs	relatime,defaults	0	0
tmpfs	/run/lock	tmpfs	rw,nosuid,nodev,noexec,relatime,size=100m	0	0
