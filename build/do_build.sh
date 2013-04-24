#!/bin/sh
#
# See README for up to date usage examples.
#

cd "$(dirname "$0")/.."
TOP="$(pwd)"

. build/nano_env
. build/functions.sh
. build/pbi_env

: ${SKIP_SOURCE_PATCHES="yes"}
: ${SKIP_PORTS_PATCHES="yes"}
: ${USE_GIT="yes"}

# Should we build?
BUILD=true

# 0 - build only what's required (src, ports, diskimage, etc).
# 1 - force src build.
# 2 - nuke the obj directories (os-base.*, etc) and build from scratch.
#FORCE_BUILD=0

# Number of jobs to pass to make. Only applies to src so far.
MAKE_JOBS=$(( 2 * $(sysctl -n kern.smp.cpus) + 1 ))
export MAKE_JOBS

# Available targets to build
BUILD_TARGETS="\
os-base \
plugins-base \
plugins/transmission \
plugins/firefly \
plugins/minidlna \
"

# Targets to build (os-base, plugins-base, plugins/<plugin>).
TARGETS=""

# Should we update src + ports?
UPDATE=true
if [ -f ${AVATAR_ROOT}/FreeBSD/.pulled ]
then
	UPDATE=false
fi

# Trace flags
TRACE=""

# NanoBSD flags
NANO_ARGS=""

GIT_CACHE="/freenas-build/trueos.git"
if [ -z "${GIT_REPO}" -a -e "${GIT_CACHE}" ] ; then
        GIT_REPO="${GIT_CACHE}"
fi
if [ -e "${GIT_REPO}" ]; then
        echo "Using local mirror in $GIT_REPO"
else
        echo "no local mirror, to speed up builds we suggest doing"
        echo "'git clone --mirror https://github.com/trueos/trueos.git into ${HOME}/freenas/git/trueos.git"
fi
GIT_PORTS_CACHE="/freenas-build/ports.git"
if [ -z "${GIT_PORTS_REPO}" -a -e "$GIT_PORTS_CACHE" ] ;then
    GIT_PORTS_REPO="$GIT_PORTS_CACHE" 
fi
if [ -e "${GIT_PORTS_REPO}" ]; then
    echo "Using local git ports mirror in $GIT_PORTS_REPO"
else
    echo "no local mirror, to speed up builds we suggest doing"
    echo "'git clone --mirror https://github.com/freenas/ports.git into ${HOME}/freenas/git/ports.git"
fi

usage() {
	cat <<EOF
usage: ${0##*/} [-aBfsux] [-j make-jobs] [-t target1] [-t target2] [ -t ...] [-- nanobsd-options]

-a		- Build all targets
-B		- don't build. Will pull the sources and show you the
		  nanobsd.sh invocation string instead. 
-f  		- if not specified, will pass either -b (if prebuilt) to
		  nanobsd.sh, or nothing if not prebuilt. If specified once,
		  force a buildworld / buildkernel (passes -n to nanobsd). If
		  specified twice, this won't pass any options to nanobsd.sh,
		  which will force a pristine build.
-j make-jobs	- number of make jobs to run; defaults to ${MAKE_JOBS}.
-s		- show build targets
-t target	- target to build (os-base, plugins-base, <plugin-name>, etc).
		  This switch can be used more than once to specify multiple targets.
-u		- force an update via csup (warning: there are potential
		  issues with newly created files via patch -- use with
		  caution).
-x		- enable sh -x debugging
EOF
	exit 1
}

show_build_targets()
{
	for _target in ${BUILD_TARGETS}
	do
		echo "${_target}"
	done
	exit 1
}

parse_cmdline()
{
	while getopts 'aBfj:st:ux' _optch
	do
		case "${_optch}" in
		a)
			TARGETS="${BUILD_TARGETS}"
			;;
		B)
			BUILD=false
			;;
		f)
			: $(( FORCE_BUILD += 1 ))
			;;
		j)
			echo ${OPTARG} | egrep -q '^[[:digit:]]+$' && [ ${OPTARG} -gt 0 ]
			if [ $? -ne 0 ]; then
				usage
			fi
			MAKE_JOBS=${OPTARG}
			;;
		s)	
			show_build_targets
			;;
		t)
			TARGETS="${TARGETS} ${OPTARG}"
			;;
		u)
			UPDATE=true
			;;
		x)
			TRACE="-x"
			;;
		\?)
			usage
			;;
		esac
	done

	shift $((${OPTIND} - 1))

	NANO_ARGS="$@"
	export NANO_ARGS
}

expand_targets()
{
	local _targets=""
	for _target in ${TARGETS}
	do
		if [ -f "${NANO_CFG_BASE}/${_target}" ]
		then
			_targets="${_targets} ${NANO_CFG_BASE}/${_target}"
		fi
	done
	TARGETS="${_targets}"

	if [ -z "${TARGETS}" ]
	then
		error "Build targets -- ${TARGETS} -- don't exist"
	fi
}

is_plugin()
{
	local _res=1
	local _target="${1}"

	if echo "${_target}" | grep -E "^${NANO_CFG_BASE}\/plugins\/" >/dev/null 2>&1	
	then
		_res=0
	fi

	return ${_res}
}

install_pbi_manager()
{
	local src="${TOP}/src/pcbsd/pbi-manager"

	if [ -f "${PBI_BINDIR}/pbi_create" ]
	then
		rm -rf "${PBI_BINDIR}"
	fi

	mkdir -p "${PBI_BINDIR}"
	cp ${src}/pbi-manager ${PBI_BINDIR}/pbi_create
	ln -f ${PBI_BINDIR}/pbi_create ${PBI_BINDIR}/pbi_add
	ln -f ${PBI_BINDIR}/pbi_create ${PBI_BINDIR}/pbi_addrepo
	ln -f ${PBI_BINDIR}/pbi_create ${PBI_BINDIR}/pbi_browser
	ln -f ${PBI_BINDIR}/pbi_create ${PBI_BINDIR}/pbi_autobuild
	ln -f ${PBI_BINDIR}/pbi_create ${PBI_BINDIR}/pbi_delete
	ln -f ${PBI_BINDIR}/pbi_create ${PBI_BINDIR}/pbi_deleterepo
	ln -f ${PBI_BINDIR}/pbi_create ${PBI_BINDIR}/pbi_icon
	ln -f ${PBI_BINDIR}/pbi_create ${PBI_BINDIR}/pbi_info
	ln -f ${PBI_BINDIR}/pbi_create ${PBI_BINDIR}/pbi_indextool
	ln -f ${PBI_BINDIR}/pbi_create ${PBI_BINDIR}/pbi_listrepo
	ln -f ${PBI_BINDIR}/pbi_create ${PBI_BINDIR}/pbi_makepatch
	ln -f ${PBI_BINDIR}/pbi_create ${PBI_BINDIR}/pbi_makeport
	ln -f ${PBI_BINDIR}/pbi_create ${PBI_BINDIR}/pbi_makerepo
	ln -f ${PBI_BINDIR}/pbi_create ${PBI_BINDIR}/pbi_metatool
	ln -f ${PBI_BINDIR}/pbi_create ${PBI_BINDIR}/pbi_patch
	ln -f ${PBI_BINDIR}/pbi_create ${PBI_BINDIR}/pbi_update
	ln -f ${PBI_BINDIR}/pbi_create ${PBI_BINDIR}/pbi_update_hashdir
	ln -f ${PBI_BINDIR}/pbi_create ${PBI_BINDIR}/pbid
	ln -f ${PBI_BINDIR}/pbi_create ${PBI_BINDIR}/pbi-crashhandler
	rm -f ${PBI_BINDIR}/pbi-manager

	PATH="${PBI_BINDIR}:${PATH}"
	export PATH
}

build_target()
{
	local _target="${1}"
	local _args="${NANO_ARGS}"
	local _nanobsd="${AVATAR_ROOT}/build/nanobsd/nanobsd.sh"
	local _fb=${FORCE_BUILD}
	local _c

	export AVATAR_COMPONENT=${_target##*/}

	#
	# XXX: chicken and egg problem. Not doing this will always cause plugins-base,
	# etc to rebuild if os-base isn't already present, or the build to fail if
	# os-base is built and plugins-base isn't, etc.
	#
	export NANO_OBJ=${AVATAR_ROOT}/${AVATAR_COMPONENT}/${NANO_ARCH}

	#
	# _fb is unset -- apply sane defaults based on what's already been built.
	#
	if [ -z "${_fb}" ]
	then
		_fb=0

		local _required_logs="_.iw"
		if [ "${AVATAR_COMPONENT}" = "os-base" ]
		then
			#
			# The base OS distro requires a kernel build.
			#
			_required_logs="_.ik _.iw"

		#
		# For plugins, we don't need to build a NanoBSD image, however, the PBI
		# tools will build a chroot and use it in the future for all plugin builds.
		#
		elif is_plugin "${_target}"
		then
			_required_logs=""
		fi

		for _required_log in ${_required_logs}
		do
			if [ ! -s "${NANO_OBJ}/${_required_log}" ]
			then
				_fb=2
				break
			fi
		done
	fi

	if [ "${_fb}" = "0" ]
	then
		_args="${_args} -b"

	elif [ "${_fb}" = "1" ]
	then
		_args="${_args} -n"
		_c=$(echo ${AVATAR_COMPONENT} | tr '-' '_')
		
		export "${_c}_FORCE=1"
	fi

	local _cmd="${_nanobsd} -c ${_target} ${_args} -j ${MAKE_JOBS}"

	if ! $BUILD
	then
		echo ${_cmd}
		exit 0
	fi

	if sh ${TRACE} ${_cmd}
	then
		echo "${NANO_LABEL} ${_target} build PASSED"
	else
		error "${NANO_LABEL} ${_target} build FAILED; please check above log for more details"
	fi
	
	return $?
}

build_targets()
{
	#
	# For now do this iteratively. Eventually it would be nice to
	# be able to background building each target, but currently
	# that needs some more kung-fu. 
	#
	cd ${NANO_SRC}
	for _target in ${TARGETS}
	do
		build_target "${_target}"
	done
}

freebsd_checkout_svn()
{
	: ${FREEBSD_SRC_REPOSITORY_ROOT=http://svn.freebsd.org/base}
	FREEBSD_SRC_URL_REL="releng/9.1"

	FREEBSD_SRC_URL_FULL="$FREEBSD_SRC_REPOSITORY_ROOT/$FREEBSD_SRC_URL_REL"

	(
	 cd "$AVATAR_ROOT/FreeBSD"
	 if [ -d src/.svn ]; then
		svn switch $FREEBSD_SRC_URL_FULL src
		svn upgrade src >/dev/null 2>&1 || :
	 	svn resolved src
	 else
		svn co $FREEBSD_SRC_URL_FULL src
	 fi
	 # Always do this so the csup pulled files are paved over.
 	 svn revert -R src
	 svn up src
	)
}

freebsd_checkout_git()
{
	(
	: ${GIT_BRANCH=freenas-9-stable}
	: ${GIT_REPO=https://github.com/trueos/trueos.git}
	cd "$AVATAR_ROOT/FreeBSD"
	if [ -d src/.git ] ; then
		cd src
		if [ "x`git rev-parse --abbrev-ref HEAD`" != "x${GIT_BRANCH}" ]; then

			git checkout ${GIT_BRANCH}
		fi
		git pull --depth 1
		cd ..
	else
		spl="$-";set -x
		git clone -b ${GIT_BRANCH} ${GIT_REPO} --depth 1 src
		echo $spl | grep -q x || set +x
		if [ "x${GIT_TAG}" != "x" ] ; then
			(
			spl="$-";set -x
			cd src && git checkout "tags/${GIT_TAG}"
			echo $spl | grep -q x || set +x
			)
		fi
	fi
	)
}

checkout_freebsd_source()
{
	if ${UPDATE}
	then
		mkdir -p ${AVATAR_ROOT}/FreeBSD

		if [ "x$USE_GIT" = "xyes" ] ; then
			echo "Use git set!"
			freebsd_checkout_git

			# Nuke newly created files to avoid build errors.
			git_status_ok="$AVATAR_ROOT/FreeBSD/.git_status_ok"
			rm -rf "$git_status_ok"
			(
			  cd $AVATAR_ROOT/FreeBSD/src && git status --porcelain
			) | tee "$git_status_ok"
			awk '$1 == "??" { print $2 }' < "$git_status_ok" |  xargs rm -Rf

			# Checkout git ports
			ports_checkout_git
		else
			echo "Use git unset!"
			freebsd_checkout_svn

			# Nuke newly created files to avoid build errors.
			svn_status_ok="$AVATAR_ROOT/FreeBSD/.svn_status_ok"
			rm -f "$svn_status_ok"
			(
			 svn status $AVATAR_ROOT/FreeBSD/src
			 : > "$svn_status_ok"
			) | \
			    awk '$1 == "?" { print $2 }' | \
			    xargs rm -Rf
			[ -f "$svn_status_ok" ]

			# Checkout cvs ports
			ports_checkout_cvs
		fi


		#
		# Force a repatch.
		#
		: > ${AVATAR_ROOT}/FreeBSD/src-patches
		: > ${AVATAR_ROOT}/FreeBSD/ports-patches
		: > ${AVATAR_ROOT}/FreeBSD/.pulled
	fi
}

ports_checkout_git()
{
	(
	cd "$AVATAR_ROOT/FreeBSD"
	if [ -d ports/.git ] ; then
		cd ports
		git pull --depth 1
		cd ..
	else
		: ${GIT_PORTS_BRANCH=master}
		: ${GIT_PORTS_REPO=git://github.com/freenas/ports.git}
		spl="$-";set -x
		git clone -b ${GIT_PORTS_BRANCH} ${GIT_PORTS_REPO} --depth 1 ports
		echo $spl | grep -q x || set +x
		if [ "x${GIT_PORTS_TAG}" != "x" ] ; then
			(
			spl="$-";set -x
			cd src && git checkout "tags/${GIT_PORTS_TAG}"
			echo $spl | grep -q x || set +x
			)
		fi
	fi
	)
}

ports_checkout_cvs()
{

	if [ -z "${FREEBSD_CVSUP_HOST}" ]
	then
		error "No sup host defined, please define FREEBSD_CVSUP_HOST and rerun"
	fi

	SUPFILE=$AVATAR_ROOT/FreeBSD/supfile
	cat <<EOF > $SUPFILE
*default host=${FREEBSD_CVSUP_HOST}
*default base=${AVATAR_ROOT}/FreeBSD/sup
*default prefix=${AVATAR_ROOT}/FreeBSD
*default release=cvs
*default delete use-rel-suffix
*default compress

ports-all date=2012.07.12.00.00.00
EOF

	for file in $(find ${AVATAR_ROOT}/FreeBSD/ports -name '*.orig' -size 0)
	do
		rm -f "$(echo ${file} | sed -e 's/.orig$//')"
	done

	echo "Checking out ports tree from ${FREEBSD_CVSUP_HOST}..."
	csup -L 1 ${SUPFILE}

}

_lp=last-patch.$$.log

patch_filter()
{
    if [ "x$USE_GIT" = "xyes" ] ; then
        sed 's/$FreeBSD[^$]*[$]/$FreeBSD$/g'
    else
        cat
    fi

}

do_source_patches()
{
for patch in $(cd $AVATAR_ROOT/patches && ls freebsd-*.patch); do
	if ! grep -q $patch $AVATAR_ROOT/FreeBSD/src-patches; then
		echo "Applying patch $patch..."
        mkdir -p filtered-patches
		(cd FreeBSD/src &&
        patch_filter < $AVATAR_ROOT/patches/$patch > $AVATAR_ROOT/filtered-patches/$patch &&
		 patch -C -f -p0 < $AVATAR_ROOT/filtered-patches/$patch >$_lp 2>&1 ||
		 { echo "Failed to apply patch: $patch (check $(pwd)/$_lp)";
		   exit 1; } &&
		 patch -E -p0 -s < $AVATAR_ROOT/filtered-patches/$patch)
		echo $patch >> $AVATAR_ROOT/FreeBSD/src-patches
	fi
done
}

do_ports_patches()
{
for patch in $(cd $AVATAR_ROOT/patches && ls ports-*.patch); do
	if ! grep -q $patch $AVATAR_ROOT/FreeBSD/ports-patches; then
		echo "Applying patch $patch..."
		(cd FreeBSD/ports &&
		 patch -C -f -p0 < $AVATAR_ROOT/patches/$patch >$_lp 2>&1 ||
		{ echo "Failed to apply patch: $patch (check $(pwd)/$_lp)";
		  exit 1; } &&
		 patch -E -p0 -s < $AVATAR_ROOT/patches/$patch)
		echo $patch >> $AVATAR_ROOT/FreeBSD/ports-patches
	fi
done
}

do_pbi_wrapper_hack()
{
	local _src="${AVATAR_ROOT}/src/pcbsd/pbi-wrapper"
	local _dst="${AVATAR_ROOT}/FreeBSD/src/pbi-wrapper"

	if [ ! -d "${_dst}" ]
	then
		mkdir -p "${_dst}"
	fi
	cp ${_src}/* ${_dst}

	NANO_LOCAL_DIRS="pbi-wrapper"
	export NANO_LOCAL_DIRS
}

main()
{
	parse_cmdline "$@"

	#
	# Assume os-base if no targets are specified
	#
	if [ -z "${TARGETS}" ]
	then
		TARGETS="os-base"
	fi

	#
	# You must be root to build FreeNAS
	#
	set -e
	if $BUILD
	then
		requires_root
	fi

	#
	# Install pbi-manager to a known location
	#
	install_pbi_manager

	#
	# Expand targets to their full path in the file system
	#
	expand_targets

	#
	# If UPDATE is set, we need to grab the FreeBSD source code
	#
	checkout_freebsd_source

	#
	# Apply source and port patches to FreeBSD source code
	#
	if [ "x${SKIP_SOURCE_PATCHES}" != "xyes" ] ; then
		do_source_patches
	fi
	if [ "x${SKIP_PORTS_PATCHES}" != "xyes" ] ; then
		do_ports_patches
	fi

	#
	# HACK: chmod +x the script because:
	# 1. It's not in FreeBSD proper, so it will always be touched.
	# 2. The mode is 0644 by default, and using a pattern like ${SHELL}
	#    in the Makefile snippet won't work with csh users because the
	#    script uses /bin/sh constructs.
	#
	if [ -f "${NANO_SRC}/include/mk-osreldate.sh.orig" ]
	then
		chmod +x ${NANO_SRC}/include/mk-osreldate.sh
	fi

	#
	# pbiwrapper hacks
	#
	do_pbi_wrapper_hack

	#
	# Now let's build the targets
	#	
	build_targets "$@"
}


main "$@"
