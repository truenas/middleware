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

usage()
{
	cat <<EOF
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
VERBOSE=0

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

if ! stage_log=$(mktemp /tmp/install_worker.XXXXXX)
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
	echo "${0##*/}: $stage summary"
	cat $stage_log
fi
rm -f $stage_log

exit $ec
