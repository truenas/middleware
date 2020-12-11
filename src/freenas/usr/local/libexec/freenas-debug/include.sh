#!/bin/sh
#+
# Copyright 2011 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################

if is_freebsd; then
	test -e /etc/rc.freenas && . /etc/rc.freenas
	test -e /etc/rc.conf.local && . /etc/rc.conf.local
fi

#
# This is the directory where we save things
#
: ${FREENAS_DEBUG_DIRECTORY:="/var/tmp/fndebug"}

#
# This is the filename of the tarball we create if sending an email
#
: ${FREENAS_DEBUG_FILE:="/var/tmp/fndebug.tgz"}

#
# This is where all freenas-debug modules are located
#
: ${FREENAS_DEBUG_MODULEDIR:="/usr/local/libexec/freenas-debug"}

#
# The modules that get loaded based on command line options
#
: ${FREENAS_DEBUG_MODULES:=""}

VERSION_FILE=$(ls /etc/version*)

syslog_debug_on()
{
	if [ ! -f /etc/syslog.conf.bak ]
	then
		mv /etc/syslog.conf /etc/syslog.conf.bak
		echo -e '*.=debug\t/var/log/debug.log' > /etc/syslog.conf
		cat /etc/syslog.conf.bak >> /etc/syslog.conf

		/etc/rc.d/syslogd onereload >/dev/null 2>&1
	fi
}

syslog_debug_off()
{
	if [ -f /etc/syslog.conf.bak ]
	then
		mv /etc/syslog.conf.bak /etc/syslog.conf
		/etc/rc.d/syslogd onereload >/dev/null 2>&1
	fi
}

sc()
{
	local file="${1}"

	if [ -s "${file}" ]
	then
		 egrep -v '^(( )+)?#' "${file}"
	fi
}

section_header()
{
	name="${1}" #expose name for use in the profiling footer

	#freenas debug is starting to take a long time on certain systems
	#start profiling how long each section takes
	#also record when the section started
	fnd_section_start_time=`date +"%s"`  #get epoch time at start of routine

	echo "$name @$fnd_section_start_time" | awk '
	function makeline(ch, len)
	{
		line = "";
		for (i = 0;i < len;i++) {
			line = line ch;
		}
		return line;
	}

	{
		name = $0;
		namelen = length(name);
		if (namelen % 2 == 1) {
			namelen += 1;
			name = name " "
		}

		barlen = 80;
		bar = makeline("-", barlen);

		tmp = barlen - namelen;

		slen = tmp / 2;
		sp = makeline(" ", slen);

		printf("+%s+\n", bar);
		printf("+%s%s%s+\n", sp, name, sp);
		printf("+%s+\n", bar);
	}'
}

section_footer()
{
	if [ $fnd_section_start_time ]; then
		fnd_section_end_time=`date +"%s"`  #get epoch time at end of routine
		#subtract to find elapsed time
		fnd_section_elapsed_time=$(($fnd_section_end_time - $fnd_section_start_time))
		echo "debug finished in $fnd_section_elapsed_time seconds for $name"
		#$dirfunc is the module name passed to us by the debug torture suite
		#
		#The information included with this output is not warranted and
	        #is also producing the wrong output at certain times.
		#There is no loss in functionality by disabling this section.	
		#if [ -n "$dirfunc" ]; then
		#	echo "command used:"
		#	modname=`echo -n "$dirfunc" | sed -e 's/_directory//'`
		#	echo  ${FREENAS_DEBUG_MODULEDIR}/$modname.sh
		#fi


	fi
	echo
	echo
}

freenas_header()
{
	if [ -e "$VERSION_FILE" ] ; then
		section_header "$(cat $VERSION_FILE)"
	else
		section_header "no version file found"
	fi

	if is_linux; then
		kernel_prefix="kernel"
	else
		kernel_prefix="kern"
	fi

	out=$(sysctl -n "$kernel_prefix".ostype)
	echo "Operating system type: ${out}"

	out=$(sysctl -n "$kernel_prefix".osrelease)
	echo "Operating system release: ${out}"

	if is_freebsd; then
		out=$(sysctl -n kern.osrevision)
		echo "Operating system revision: ${out}"

		out=$(sysctl -n kern.bootfile)
		echo "Name of kernel file booted: ${out}"
	fi

	out=$(sysctl -n "$kernel_prefix".version)
	echo "Kernel version: ${out}"

	out=$(sysctl -n "$kernel_prefix".hostname)
	echo "Hostname: ${out}"

	section_footer
}

is_function()
{
	local name="${1}"

	if ! $(type "${name}" 2>/dev/null|grep -q 'shell function')
	then
		return 1
	fi

	return 0
}

is_valid_module()
{
	local name="${1}"
	local ret=0

	if ! is_function "${name}_func"
	then
		ret=1
	fi

	if ! is_function "${name}_opt"
	then
		ret=1
	fi

	if ! is_function "${name}_help"
	then
		ret=1
	fi

	return ${ret}
}

is_loaded()
{
	local ret=1
	local name="${1}"

	if [ -z "${name}" ]
	then
		return ${ret}
	fi

	for m in ${FREENAS_DEBUG_MODULES}
	do
		if [ "${name}" = "${m}" ]
		then
			ret=0
			break
		fi
	done

	return ${ret}
}

load_module()
{
	local ret=1
	local name="${1}"
	local d="${FREENAS_DEBUG_MODULEDIR}"
	local p="${d}/${name}"

	# Some modules might be linux/freebsd specifc
	# their directory names end with their respective suffixes
	# however the scripts would be stripped of the suffixes
	# and we should ensure we handle this as desired
	for suffix in "_freebsd" "_linux";
	do
		name=${name%"$suffix"}
	done

	local m="${p}/${name}.sh"

	if [ -z "${name}" ]
	then
		return ${ret}
	fi

	if [ -d "${p}" -a -f "${m}" ]
	then
		. "${m}"
	fi

	if ! is_valid_module "${name}"
	then
		unset -f $(echo "${name}_opt")
		unset -f $(echo "${name}_help")
		unset -f $(echo "${name}_func")

	elif ! is_loaded "${name}"
	then

		FREENAS_DEBUG_MODULES="${FREENAS_DEBUG_MODULES} ${name}"
		export FREENAS_DEBUG_MODULES
		ret=0
	fi

	return ${ret}
}

unload_module()
{
	local name="${1}"

	if [ -z "${name}" ] || ! is_loaded "${name}"
	then
		return 1
	fi

	unset -f $(echo "${name}_opt")
	unset -f $(echo "${name}_help")
	unset -f $(echo "${name}_func")

	FREENAS_DEBUG_MODULES=$(echo "${FREENAS_DEBUG_MODULES}"|sed "s|[[:<:]]${name}[[:>:]]||g")
	export FREENAS_DEBUG_MODULES

	return 0
}
