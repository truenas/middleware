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

# KPM - 6-5-2015 - Pulled from poudriere so we can build ports on -CURRENT
# Set specified version into login.conf
update_version_env() {
	local release="$1"
	local login_env osversion
                
	osversion=`awk '/\#define __FreeBSD_version/ { print $3 }' ${NANO_WORLDDIR}/usr/include/sys/param.h`
	login_env=",UNAME_r=${release% *},UNAME_v=FreeBSD ${release},OSVERSION=${osversion}"
        
	sed -i "" -e "s/,UNAME_r.*:/:/ ; s/:\(setenv.*\):/:\1${login_env}:/" ${NANO_WORLDDIR}/etc/login.conf
	cap_mkdb ${NANO_WORLDDIR}/etc/login.conf
}  

freenas_legacy_build() {
	local ret=1

	. build/nano_env

	if [ "${FREEBSD_RELEASE_MAJOR_VERSION}" -lt "10" \
		-a "${SYSTEM_RELEASE_MAJOR_VERSION}" -ge 11 ]
	then
		ret=0
	fi

	return ${ret}
}


