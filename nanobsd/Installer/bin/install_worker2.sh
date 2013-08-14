#!/bin/sh
#
# An generalized wrapper to be invoked at various stages of an installation or
# upgrade process.
#
# Written in shell for simplicity and to be runnable across multiple versions
# of software with minimal dependencies outside of the base system.
#
# Garrett Cooper, March 2012

# The base directory where all of the scripts and the payload are.
SCRIPTDIR=$(realpath "$(dirname "$0")/..")
. "$SCRIPTDIR/lib/functions.sh"

set -x

#
# Try to log output of this script.
#  try first logger,
#  if that fails try to fall back to a file,
#  if that fails then I guess stdout/stderr is as
#     good as it gets.
redirect_output_to_logger()
{
	# below we can run ourselves to reset output 
	# redirection, so prevent infinite recursion
	# by using an env variable.
	if [ "x$INSTALLER_REDIRECTING" != "x" ] ; then
		return 0
	fi

	# Try to redirect everything to logger(1)
	FIFO_DIR=`mktemp -d -t instfifo`
	if [ $? != 0 ] ; then
	    warn "mktemp for fifo failed, logging to logger disabled."
	    return 1
	fi

	# if mkfifo isn't available, then try to
	# run a copy of ourself with output tee(1)'d
	# to a file
	if [ ! -x /usr/bin/mkfifo -o ! -x /usr/bin/logger ] ; then
	    if [ ! -x /usr/bin/tee ] ; then
		return 1
	    fi
	    warn "mkfifo/logger not available, using logfile"
	    export INSTALLER_REDIRECTING=TRUE
	    $0 ${1+"$@"} 2>&1 | tee $FIFO_DIR/install.log
	    exit $?
	fi

	FIFO="$FIFO_DIR/logger_fifo"
	mkfifo $FIFO
	if [ $? != 0 ] ; then
	    warn "mkfifo failed, logging to logger disabled."
	    return 1
	fi
	cat $FIFO | tee $FIFO_DIR/install.log | logger &
	exec >$FIFO 2>&1
	return 0
}

redirect_output_to_logger ${1+"$@"}

usage()
{
	cat <<EOF >&4
usage: ${0##*/} [-D dir] [-f expr] [-m dir] stage
===============================================================================
-D dir		: destdir to compare against. Defaults to "/".

-f expr		: a find(1) compatible regular expression used for
		  blacklisting scripts that would be normally executed in the
		  current stage.

		  Good for 1. avoiding potentially problematic scripts, or
		  2. Explicitly skipping over a stage script, e.g. say you
		  specified in an upgrade that you wanted to avoid executing
		  an automatic zpool upgrade script -- and you understood the
		  consequences of doing so.

		  This option can be specified multiple times.

-m dir		: srcdir to compare against. Defaults to "$SCRIPTDIR".

"stage" can be:
		- pre-install
		- install
		- post-install

EOF
	exit 1
}

# The directory with all of the files to compare against.
BLACKLIST_EXPR=
INSTALL_DESTDIR="/"
INSTALL_SRCDIR=$SCRIPTDIR
VERBOSE=1

while getopts 'D:f:m:v' opt
do
	case "$opt" in
	D)
		if [ ! -d "$OPTARG" ]
		then
			error "Destdir specified -- $OPTARG -- does not exist"
		fi
		INSTALL_DESTDIR=$(realpath "$OPTARG")
		;;
	f)
		BLACKLIST_EXPR="$BLACKLIST_EXPR \! -and -regexp '$OPTARG'"
		;;
	m)
		if [ ! -d "$OPTARG" ]
		then
			error "Srcdir specified -- $OPTARG -- does not exist"
		fi
		INSTALL_SRCDIR=$OPTARG
		;;
	v)
		: $(( VERBOSE += 1 ))
		;;
	*)
		usage
		;;
	esac
done
shift $(( $OPTIND - 1 ))

INSTALL_DESTDIR=$(realpath "$INSTALL_DESTDIR")
INSTALL_SRCDIR=$(realpath "$INSTALL_SRCDIR")

stage=$1
cd "$SCRIPTDIR"
if [ -z "$stage" -o ! -d "$stage" -o $# -ne 1 ]
then
	usage
fi

if ! source_conf "$INSTALL_SRCDIR/etc/avatar.conf" NEW
then
	error "Could not load the avatar.conf file from the source directory ($INSTALL_SRCDIR/etc)"
fi
if ! source_conf "$INSTALL_DESTDIR/etc/avatar.conf" OLD
then
	error "Could not load the avatar.conf file from the destination directory ($INSTALL_DESTDIR/etc)"
fi

if ! stage_log=$(mktemp -t install_worker.XXXXXX)
then
	exit 1
fi

ec=0
for script in $(find "$stage" -name '*.sh' $BLACKLIST_EXPR | sort)
do
	vecho "${0##*/}: INFO: sourcing $script"
	(. $script)
	saved_ec=$?
	if [ $saved_ec -ne 0 ]
	then
		ec=$saved_ec
	fi
done 2> $stage_log

# Gather all data possible and spit it out at the end.
if [ -s $stage_log ]
then
	necho "${0##*/}: $stage summary"
	cat $stage_log
fi
rm -f $stage_log

exit $ec
