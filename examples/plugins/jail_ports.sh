#!/bin/sh

export BATCH=yes
export WITHOUT_X11=yes

add_port()
{
	local port=$1
	local args="WITHOUT_X11=yes BATCH=yes $2"
	local targets="all deinstall install clean"

	echo "BUILDING ${port}"
	cd /usr/ports/${port}
	
	for t in ${targets}
	do
		make ${args} ${t}
	done

	echo "DONE"
}

add_port converters/libiconv
add_port converters/iconv
add_port devel/gettext
add_port lang/perl5.12
add_port databases/db46
add_port lang/python27 WITH_HUGE_STACK_SIZE=y
add_port dns/py-dnspython
add_port databases/tdb
add_port devel/pcre
add_port databases/sqlite3
add_port databases/py-sqlite3
add_port databases/py-bsddb3
add_port devel/py-setuptools
add_port devel/py-asn1
add_port devel/py-asn1-modules
add_port www/py-flup
add_port textproc/libxml2
add_port textproc/py-libxml2
add_port textproc/expat2
add_port devel/libltdl
add_port devel/py-ipaddr
add_port converters/base64
add_port devel/dbus
add_port devel/dbus-glib
add_port devel/libdaemon
add_port databases/gdbm
add_port textproc/py-xml
add_port ftp/wget
add_port devel/py-lockfile
add_port devel/py-daemon
