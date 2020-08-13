<%
	ups_config = middleware.call_sync('ups.config')
	shutdown = ups_config['shutdown']
	sudo_path = "/usr/bin/sudo" if IS_LINUX else "/usr/local/bin/sudo"
%>\
CMDSCRIPT   "${sudo_path} /usr/local/bin/custom-upssched-cmd"
PIPEFN      ${"/var/run/nut/upssched.pipe" if IS_LINUX else "/var/db/nut/upssched.pipe"}
LOCKFN      ${"/var/run/nut/upssched.lock" if IS_LINUX else "/var/db/nut/upssched.lock"}

AT NOCOMM   * EXECUTE NOTIFY-NOCOMM
AT COMMBAD  * START-TIMER NOTIFY-COMMBAD 10
AT COMMOK   * CANCEL-TIMER NOTIFY-COMMBAD COMMOK
AT FSD      * EXECUTE NOTIFY-FSD
AT LOWBATT  * EXECUTE NOTIFY-LOWBATT
AT ONBATT   * EXECUTE NOTIFY-ONBATT
AT ONLINE   * EXECUTE NOTIFY-ONLINE
AT REPLBATT * EXECUTE NOTIFY-REPLBATT
AT SHUTDOWN * EXECUTE NOTIFY-SHUTDOWN
% if shutdown.lower() == 'batt':
AT ONBATT   * START-TIMER SHUTDOWN ${ups_config['shutdowntimer']}
AT ONLINE   * CANCEL-TIMER SHUTDOWN
% elif shutdown.lower() == 'lowbatt':
AT LOWBATT  * EXECUTE SHUTDOWN
% endif
