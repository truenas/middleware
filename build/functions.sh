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
