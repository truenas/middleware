#!/bin/sh -f
#
# Copyright (c) 2014, Emanuel Haupt <ehaupt@FreeBSD.org>
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#
# $Id$

# Use a line break as delimiter.
IFS='
'

# Filename prefix for shared data
sharedprefix="/tmp/$$"
shared="locks"

#
# This function remembers a lock to allow later deletion with the
# lockUnregisterAll() function.
# 
# @param $1
#       The name of the lock.
lockRegister() {
        local lock
        lock="$sharedprefix-$shared"
        lockf -k "$lock" sh -c "
                if ! grep -qE '^$1\$' '$lock'; then
                        echo '$1' >> '$lock'
                fi
        "
}

#
# Unregisters all locks.
#
lockUnregisterAll() {
        wait
        for register in $(cat "$sharedprefix-$shared"); {
                lockf "$sharedprefix-$register" wait
        }
        lockf "$sharedprefix-$shared" wait
}

#
# This function creates a semaphore.
#
# @param $1
#       The name of the semaphore.
# @param $2
#       The size of the semaphore.
#
semaphoreCreate() {
        local lock
        lockRegister "semaphore-$1"
        lock="$sharedprefix-semaphore-$1"
        lockf -k "$lock" echo "$2" > "$lock"
        eval "semaphore_$1_size=$2"
}

#
# This function waits until the semaphore is free und registers its use.
# Everything that uses this also has to call the semaphoreFree() function.
#
# @param $1
#       The name of the semaphore.
#
semaphoreUse() {
        local lock semaphores
        lock="$sharedprefix-semaphore-$1"
        while ! lockf -k "$lock" sh -c "
                        state=\$(cat '$lock')
                        if [ \"\$state\" -gt 0 ]; then
                                echo \"\$((\$state - 1))\" > '$lock'
                                exit 0
                        fi
                        exit 1
                "; do
                sleep 0.1
        done
}

#
# This function frees a semaphore.
#
# @param $1
#       The name of the semaphore.
#
semaphoreFree() {
        local lock
        lock="$sharedprefix-semaphore-$1"
        lockf -k "$lock" sh -c "
                state=\"\$((\"\$(cat '$lock')\" + 1))\"
                echo \"\$state\" > '$lock'
        "
}

#
# This function sets a new status and prints it.
#
# @param $1
#       The status message.
# @param $clean
#       If set status handling is disabled.
#
statusSet() {
        # In clean mode status handling is disabled.
        test -z "$clean" || return 0
        local lock
        lock="$sharedprefix-status"
        lockf -k "$lock" sh -c "
                status=\"\$(cat '$lock')\"
                echo '$1' > '$lock'
                printf \"\\r%-\${#status}s\\r\" '$1' > /dev/tty
        "
}

#
# This function prints a message and the current status behind it.
#
# @param $1
#       The message to print.
# @param $clean
#       If set the status will not be printed.
#
statusPrint() {
        if [ -z "$clean" ]; then
                local lock
                lock="$sharedprefix-status"
                lockf -k "$lock" sh -c "
                        status=\"\$(cat '$lock')\"
                        printf \"%-\${#status}s\\r\" '' > /dev/tty
                        echo '$1'
                        printf '%s\\r' \"\$status\" > /dev/tty
                "
        else
                echo "$1"
        fi
}

# Waits for a semaphore to be completely free and counts down the remaining
# number of locks.
#
# @param $1
#       The semaphore to watch.
# @param $2
#       The status message to print, insert %d in the place where the number
#       of remaining locks belong.
#
semaphoreCountDown() {
        local free size
        while read -t1 free < "$sharedprefix-semaphore-$1"; do
                size=$(eval "echo \$semaphore_$1_size")
                statusSet "$(printf "$2" $(( $size - $free )))"
                test "$free" -eq "$size" && break
                sleep 0.1
        done
        wait
}

# Clean up upon exit.
trap '
        semaphoreCountDown jobs "Terminated by signal, waiting for %d jobs to die."
        echo > /dev/tty
        lockUnregisterAll
        exit 255
' int term

usage() {
	cat << EOF
`basename $0` [option] -d dir
      -d dir        output directory
      -t n          http/ftp timeout
      -v            verbose

EOF
}

readParams() {
	while getopts "cvhd:t:" FLAGS; do
		case "${FLAGS}" in
			c)
				clean=1
			;;
			d)
				distdir=${OPTARG}
				if [ ! -d "${distdir}" ]; then
					echo "${distdir} directory does not exist."
					exit 3
				fi
			;;
			h)
				usage
				exit 0
			;;
			t)
				HTTP_TIMEOUT=${OPTARG}
				FTP_TIMEOUT=${OPTARG}
			;;
			v)
				verbose=1
			;;
		esac
	done

	if [ -z "${distdir}" ]; then
		echo "Must specify output dir."
		usage
		exit 3
	fi
}

# Create the semaphore with CPU cores * 2 jobs.
semaphoreCreate jobs "$(($(sysctl -n hw.ncpu 2> /dev/null || echo 1) * 2))"
# Register the status lock.
lockRegister status

# Read the parameters.
readParams "$@"

statusSet 'Preparing ...'

fetchDistfiles() {
	local port="$1"

	if [ -n "$verbose" ]; then
		echo $HTTP_TIMEOUT
		echo $FTP_TIMEOUT
		BATCH=yes TRYBROKEN=yes PACKAGE_BUILDING=yes DISTDIR="${distdir}" make -C${port} fetch
	else
		BATCH=yes TRYBROKEN=yes PACKAGE_BUILDING=yes DISTDIR="${distdir}" make -C${port} fetch > /dev/null 2>&1
	fi

	return $?
}

index_file="/usr/ports/`make -C/usr/ports -VINDEXFILE`"
ports_amount="$(wc -l ${index_file} | awk '{print $1}')"
ports_num=0

for port in $(awk 'FS="|" {print $2}' ${index_file}); {
	ports_num="$(($ports_num + 1))"

	# Print what we're doing.
	statusSet "Starting job $ports_num of $ports_amount: $port"

	semaphoreUse jobs
	(
		# Remember freeing the semaphore.
		trap 'semaphoreFree jobs' EXIT

		fetchDistfiles $port
		if [ "$?" != 0 ]; then
			statusPrint "$port failed to fetch."
		fi
	) &
}

semaphoreCountDown jobs "Waiting for %d remaining jobs to finish."
statusSet
lockUnregisterAll

exit 0
