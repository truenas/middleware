<%
    import glob

    enabled = middleware.call_sync2(middleware.services.system.advanced.config).kdump_enabled

    if enabled:
        initrd_list = glob.glob('/boot/initrd.img*')
        if not initrd_list:
            middleware.logger.error('Initrd image not found under /boot.')
            enabled = False
        else:
            initrd_boot_path = initrd_list[0]
%>\
% if enabled:
USE_KDUMP=1
KDUMP_INITRD=${initrd_boot_path}
% else:
USE_KDUMP=0
% endif
KDUMP_KERNEL=/var/lib/kdump/vmlinuz
KDUMP_COREDIR=/var/crash
