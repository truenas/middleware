#!/bin/sh
#
# Basic installer scripting infrastructure.
#
# Garrett Cooper, March 2012

LOGGER=1

error()
{
	echo >&3 "${0##*/}: ERROR: $@"
	exit 1
}

myecho()
{
    local _type
    _type="$1"
    shift
    echo "${0##*/}: ${_type}: $@"
}

# verbose echo
vecho()
{
	if [ "$VERBOSE" != "0" ]
	then
        myecho "INFO:" "$@"
	fi
}

# normal echo
necho()
{
    myecho "INFO:" "$@"
}

warn()
{
	echo >&3 "${0##*/}: WARNING: $@"
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
	local project1=$1
	local project2=$2

	if [ -z "$project1" -o "$project1" = "$project2" ]
	then
		return 0
	fi
	return 1
}

# Extract just the version fields from the version.
# We convert string "9.0.7-RELEASE-DEBUG-p4-r8863" -> "9.0.7-4-8863"
# so that we can sort on it.
#
# Note there are many versions we expect:
#
# 9.0.7-RELEASE-DEBUG-p4-r8863
# 9.0.7-RELEASE-p4-r8863
# 9.0.7-RELEASE-r8863
# 9.0.7-RELEASE-r8863M
# 9.0.7-RELEASE-DEBUG-p4-r8863/fgfg34
# etc
#
# we will normalize it to:
#  major-patchlevel
#
# note, if there is no patchlevel, example: 9.0.7-RELEASE-r8863, we emit
# a normalized string with a zero in it: 9.0.7-0-8863.
get_ver_fields()
{
    local _VER

    read _VER

    # check for -p[0-9] (patchlevel)
    echo "$_VER" | grep -Eq -- '-p[0-9]*-'
    # if there is no substring of -p0- then insert one.
    if [ $? -eq 1 ] ; then
        # emit all the fields except insert '-p0-' before the last one
        _VER=`echo "$_VER" | awk 'BEGIN{FS="-";}{for(i = 1; i < NF;i++){printf("%s-",$i)};printf("p0-%s",$NF)}'`
        #echo "VER: $_VER " >/dev/stderr
    fi

    # Now do some regex to normalize.
    #  The first sed invocation does the following actions
    #   1. remove -DEBUG- if it exists.
    #   2. replace the patchlevel -pN- with just -N-
    #  The second sed invocation normalizes the svnrev and possible
    #   git hash to just the svnrev removing any "M" noting that the
    #   the working copy has been modified.
    #  Note: we discard the svnrev, this is just kept for now in case
    #  we need it later
    # Finally select the fields we are after using cut(1).
    echo "$_VER" | sed -e 's,-DEBUG,,' \
        -e 's,-p\([0-9]\)*-,-\1-,g' \
        | sed -E -e 's,-r([0-9]*)M?(/[a-z0-9]*)?,-\1,' \
        | cut -f 1,3 -d-
}

# use a stable sort to maintain proper ordering.
# This function is used to sort the normalized output of two version
# strings
sort_ver_fields()
{
    sort -n -s -k $1 -f '-'

}

# Compare two arbitrary versions to return whether or not one is newer than
# the other.
#
# Parameters:
# 1 - version1
# 2 - version2
#
# The expected format is:
#    9.0.7-RELEASE-p4-r8865/abfg34
#    9.0.7-RELEASE-r8865/abfg34
#
# Note: we only compare the major version and patchlevel, so the significant
# parts are "9.0.7" and "p4"
#
# We used to compare the svnrevision but do not anymore because it is not
# useful in TrueNAS and can hurt us doing development and hot fixes for
# clients.

#
# Returns:
# 0 - version1 == version2
# 1 - version1 < version2
# 2 - version1 > version2
compare_version()
{
    local version1=`echo $1 | get_ver_fields`
    local version2=`echo $2 | get_ver_fields`

    #echo "v1: $version1"
    #echo "v2: $version2"

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

     unsorted="$version1 $version2"
     # Sort on the keys in this order:
     #  patchlevel, release number
     sorted=$(echo $unsorted | tr ' ' '\n' | sort_ver_fields 2 | sort_ver_fields 1 | tr '\n' ' ')

     #echo "unsorted: $unsorted"
     #echo "sorted: $sorted"

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

	if ! tmpconf=$(mktemp -t conf.XXXXXX)
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
