<%
	advanced = middleware.call_sync('system.advanced.config')
	serial_speed = f'.{advanced["serialspeed"]}' if advanced['serialconsole'] else ''
	ttyv = 'freenas' if advanced['consolemenu'] else 'freenas.115200'
	ttyu = f'freenas{serial_speed}' if advanced['consolemenu'] else f'3wire{serial_speed}'

	# Forcefully enable TTY on configured UART port in case it
	# is different from console port.  It may happen since we
	# can not enable/change serial console port without reboot.
	serdev = ''
	if advanced['serialconsole']:
		dev_serial = list(
			filter(
				lambda i: i['name'].startswith('uart') and int(i['start'], 16) <= int(advanced['serialport'], 16) < int(i['start'], 16) + i['size'],
				middleware.call_sync('device.get_info', 'SERIAL')
			)
		)
		if dev_serial:
			serdev = dev_serial[0]['name'].replace('uart', 'ttyu')
%>\
#
# $FreeBSD: src/etc/etc.amd64/ttys,v 1.18.2.1 2009/08/03 08:13:06 kensmith Exp $
#	@(#)ttys	5.1 (Berkeley) 4/17/89
#
# This file specifies various information about terminals on the system.
# It is used by several different programs.  Common entries for the
# various columns include:
#
# name  The name of the terminal device.
#
# getty The program to start running on the terminal.  Typically a
#       getty program, as the name implies.  Other common entries
#       include none, when no getty is needed, and xdm, to start the
#       X Window System.
#
# type The initial terminal type for this port.  For hardwired
#      terminal lines, this will contain the type of terminal used.
#      For virtual consoles, the correct type is typically xterm.
#      Other common values include dialup for incoming modem ports, and
#      unknown when the terminal type cannot be predetermined.
#
# status Must be on or off.  If on, init will run the getty program on
#        the specified port.  If the word "secure" appears, this tty
#        allows root login.
#
# name	getty				type	status		comments
#
# If console is marked "insecure", then init will ask for the root password
# when going to single-user mode.
console	none				unknown	off secure
#
ttyv0	"/usr/libexec/getty ${ttyv}"	xterm	onifexists  secure
# Virtual terminals
ttyv1	"/usr/libexec/getty Pc"		xterm	onifexists  secure
ttyv2	"/usr/libexec/getty Pc"		xterm	onifexists  secure
ttyv3	"/usr/libexec/getty Pc"		xterm	onifexists  secure
ttyv4	"/usr/libexec/getty Pc"		xterm	onifexists  secure
ttyv5	"/usr/libexec/getty Pc"		xterm	onifexists  secure
ttyv6	"/usr/libexec/getty Pc"		xterm	onifexists  secure
ttyv7	"/usr/libexec/getty Pc"		xterm	onifexists  secure
ttyv8	"/usr/local/bin/xdm -nodaemon"	xterm	off secure
# Serial terminals
# The 'dialup' keyword identifies dialin lines to login, fingerd etc.
% for i in range(4):
ttyu${i}	"/usr/libexec/getty ${ttyu}"	vt100	${'onifconsole' if f'ttyu{i}' != serdev else 'on'} secure
% endfor
# Dumb console
dcons	"/usr/libexec/getty std.9600"	vt100	off secure

#zfsd	"/sbin/zfsd -d"		unknown	on	secure
