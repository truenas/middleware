#
# General purpose functions.
#

error() {
	echo >&2 "${0##*/}: ERROR: $*"
	exit 1
}

info() {
	echo "${0##*/}: INFO: $*"
}

#nano_env_vars() {
#	grep '^export' "$AVATAR_ROOT/build/nano_env" | \
#	    sed -e 's/export //g' | tr '\012' ' '
#}

requires_root() {
	if [ $(id -ru) -ne 0 ]; then
		error "You must be root when running $0"
	fi
}

eargs() {
	case $# in
	0) err 1 "No arguments expected" ;;
	1) err 1 "1 argument expected: $1" ;;
	*) err 1 "$# arguments expected: $*" ;;
	esac
}

umountfs() {
	[ $# -lt 1 ] && eargs mnt childonly
	local mnt=$1
	local childonly=$2
	local pattern

	[ -n "${childonly}" ] && pattern="/"

	[ -d "${mnt}" ] || return 0
	mnt=$(realpath ${mnt})
	mount | sort -r -k 2 | while read dev on pt opts; do
		case ${pt} in
		${mnt}${pattern}*)
			umount -f ${pt} || :
			[ "${dev#/dev/md*}" != "${dev}" ] && mdconfig -d -u ${dev#/dev/md*}
		;;
		esac
	done

	return 0
}
