#!/bin/sh
#
# Basic installer scripting infrastructure.
#
# Garrett Cooper, March 2012

error()
{
	echo >&2 "${0##*/}: ERROR: $@"
	exit 1
}

vecho()
{
	if [ $VERBOSE -gt 0 ]
	then
		echo "${0##*/}: INFO: $@"
	fi
}

warn()
{
	echo >&2 "${0##*/}: WARNING: $@"
}

sysctl_n()
{
	sysctl -n $*
}

# Compare two projects to see whether or not they're the same.
#
# Parameters:
# 1 - project1
# 2 - project2
#
# Returns:
# 0 - project1 == project2
# 1 - project1 != project2
compare_project()
{
	project1=$1
	project2=$2

	if [ -z "$project1" -o "$project1" = "$project2" ]
	then
		return 0
	fi
	return 1
}

# Phases in a release cycle sorted in chronological order.
#
# See rewrite_release_phases for more details.
readonly RELEASE_PHASES="
ALPHA
BETA
RC
PRERELEASE
RELEASE
"

# In order for sort(1) to do the right thing with release versions below, we
# need to remap the "release phases" (ALPHA, BETA, RC, PRERELEASE, RELEASE) to
# their respective numeric stages in the release cycle so the numeric sort will
# succeed.
#
# This function also sanity checks that the version string matches the expected
# release phase format.
#
# Parameters:
# 1 - version string to rewrite
rewrite_release_phases()
{
	local i
	local version_string
	local version_string_old

	version_string=$1
	version_string_old=$1

	i=0
	set -- $RELEASE_PHASES
	while [ $# -gt 0 ]
	do
		version_string=$(echo "$version_string" | sed -e "s/$1/$i./")
		shift
		: $(( i += 1 ))
	done

	# Sanity check
	if [ $version_string = $version_string_old ]
	then
		error "version string was unexpected ($version_string).

It must contain one of the following strings:
$RELEASE_PHASES"
	fi
	echo $version_string
}

# Compare two arbitrary versions to return whether or not one is newer than
# the other.
#
# Parameters:
# 1 - version1
# 2 - version2
#
# Returns:
# 0 - version1 == version2
# 1 - version1 < version2
# 2 - version1 > version2
compare_version()
{
	local version1 version2 unsorted sorted
	# X.X.X-PHASE
	# FIXME: patchsets (-p1, -p2, etc)
	version1=$1
	version2=$2

	if [ -z "$version2" ]
	then
		error "malformed upgrade version specified (is NIL)"
	fi

	# Consider empty version as smaller.
	if [ -z "$version1" ]
	then
		return 1
	fi

	if [ "$version1" = "$version2" ]
	then
		return 0
	fi

	version1=$(rewrite_release_phases $version1)
	version2=$(rewrite_release_phases $version2)

	unsorted="$version1 $version2"
	# Magic sort fu required for 9.0.0 vs 10.0.0, etc.
	sorted=$(echo -n $unsorted | tr ' ' '\n' | sort -k 1 -f '-' -n | tr '\n' ' ')

	# NOTE: sort adds on a '\n' at EOL.
	if [ "$sorted" = "$unsorted " ]
	then
		return 1
	fi
	return 2
}

# Source an avatar configuration file
#
# Parameters:
# 1 - .conf file to source.
# 2 - prefix for variables (e.g. NEW, OLD, etc).
#
# Returns:
# 0 if successful; 1 otherwise
source_conf()
{
	local IFS conffile prefix tmp

	conffile=$1
	prefix=$2

	if [ ! -f "$conffile" -o -z "$prefix" ]
	then
		return 1
	fi

	if ! tmpconf=$(mktemp /tmp/conf.XXXXXX)
	then
		return 1
	fi

	# 1. Skip over comments and empty/whitespace lines.
	# 2. Skip over export lines.
	# 3. Prefix lines with "$prefix".
	sed -E \
	    -e 's/#.*//g' \
	    -e '/^[[:space:]]*$/d' \
	    -e '/^export /d' \
	    -e "s/^/${prefix}_/g" "$conffile" \
	    > $tmpconf

	# Taint the environment.
	. $tmpconf
	rc=$?

	rm -f $tmpconf

	return $rc
}
