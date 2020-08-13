# /etc/crontab - root's crontab for FreeBSD
#
# $FreeBSD: src/etc/crontab,v 1.33.2.1 2009/08/03 08:13:06 kensmith Exp $
#
SHELL=/bin/sh
PATH=/etc:/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin
#
#minute	hour	mday	month	wday	who	command
#
*/5	*	*	*	*	root	/usr/libexec/atrun > /dev/null 2>&1
#
# Save some entropy so that /dev/random can re-seed on boot.
*/11	*	*	*	*	operator /usr/libexec/save-entropy > /dev/null 2>&1
#
# Rotate log files only at midnight.
0	0	*	*	*	root	newsyslog > /dev/null 2>&1
#
# Adjust the time zone if the CMOS clock keeps local time, as opposed to
# UTC time.  See adjkerntz(8) for details.
1,31	0-5	*	*	*	root	adjkerntz -a > /dev/null 2>&1

0	*	*	*	*	root	/usr/local/bin/python /usr/local/bin/mfistatus.py > /dev/null 2>&1

30	*/5	*	*	*	root	/etc/ix.rc.d/ix-kinit renew > /dev/null 2>&1
