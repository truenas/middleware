#!/bin/sh
#
# A basic svn automerger tool.
#
# Copyright (c) 2011-2012 iXsystems, Inc., All rights reserved.
#
# NOTES:
# 1. It's highly advised to run this with lockf, similar to the following:
#
# /usr/bin/lockf -k -t 600 /build/automerge/f/branches/8.2.0/.old_version \
#	/bin/sh \
#	/build/automerge/f/trunk/tools/automerge.sh /build/automerge/f \
#	trunk branches/8.2.0
#
#    Otherwise 2+ instances of this script can stomp over one another, which
#    will result in interesting issues based on how svn locking works.
#
# 2. You should not run this script on a tainted workspace as it will whack
#    files not checked into svn (minus .old_version and .new_version, for
#    obvious reasons below).
#
# 3. This script helps manage merging for multiple target branches. If you
#    have a commit that you do not wish to be automatically merged to another
#    branch, please use one of the following options:
#
# Option 1:
#
# Do-Not-Merge: message
#
# Option 2:
#
# Do-Not-Merge (branches/8.2.0,branches/stable-8): message
#
# Option 1 is a blatant "do not merge me anywhere" tag. Its intent was
# originally to ensure that commits made to SF trunk didn't make it into the
# ix repo automatically.
#
# Option 2 is a bit more interesting: its intent was to make sure that a
# select set of commits made to a particular branch (say SF trunk) were
# propagated over to the ix repo, but not necessarily other branches (say
# branches/8.2.0). Multiple branches can be specified via a comma-delimited
# list. In the above example, the commit would be propagated anywhere but
# branches/8.2.0 and branches/stable-8
#
# Please note that 'Do-Not-Merge' must be specified at the start of any given
# line -- not elsewhere in the file.
#
# XXX: this script is far from perfect. It's just a stopgap to avoid having
#      to manually merge files in svn.
#
# Garrett Cooper, November 2011

export PATH=/bin:/usr/bin:/usr/local/bin

set -eu

# A graceful means for doing SVN because we ran into issues pulling from SF
# svn from time to time (high latency, large potential for partial merges).
_do() {
	local ec log tries

	log=log.$$

	ec=1
	tries=5

	: > $log
	while [ $tries -gt 0 ]
	do
		$* > $log 2>&1
		if awk 'BEGIN { ec=1 } $1 == "C" || $2 == "C" { ec=0 } END { exit ec }' $log
		then
			break
		elif ! grep -q 'svn: E' $log
		then
			ec=0
			break
		fi
		: $(( tries -= 1 ))
	done
	cat $log
	rm -f $log
	return $ec
}

clean_svn() {
	_do svn cleanup $parent_branch
	_do svn cleanup $child_branch
	_do svn revert -R $child_branch
	# Nuke everything in the directory that's not supposed to be there. Be
	# sure to preserve FreeBSD, obj.* directories, and .new_version, and
	# .old_version files to get things back to a sane state.
	_do svn status $child_branch | \
		awk '$1 == "?" && $2 !~ /FreeBSD/ && $2 !~ /obj\./ { print $2 }' | \
		egrep -v '(new|old)_version' | xargs rm -Rf
}

usage() {
	cat <<EOF
usage: ${0##*/} [-Dn] base-dir parent-branch child-branch

-D	- do not honor Do-Not-Merge 'tags'.
-n	- fake committing (good for testing ;)..).

EOF
	exit 1
}

fake_commit=false
honor_do_not_merge=true

while getopts 'Dn' optch
do
	case "$optch" in
	D)
		honor_do_not_merge=false
		;;
	n)
		fake_commit=true
		;;
	*)
		usage
		;;
	esac
done

shift $(( $OPTIND - 1 ))

if [ $# -ne 3 ]
then
	usage
fi
base_dir=$1
parent_branch=$2
child_branch=$3

cd $base_dir

# Cached version files for the parent branch.
#
# Please note that while (for sanity/cleanliness), it would be better for these
# files to live under the parent branch, the problem that needs to be resolved
# here is that you can have a parent branch which is consumed by multiple child
# branches. So in order for everything to live and operate on multiple branches
# in the same repo, we must store these files in the target path, not the
# source path.
#
# Sorry in advance for any confusion...
OLD_VERSION_F=$(realpath "$child_branch/.old_version")
NEW_VERSION_F=$(realpath "$child_branch/.new_version")

# XXX: doesn't work like expected.
#lockf -k -t 1 .old_version true
old_version=$(cat $OLD_VERSION_F)
clean_svn
_do svn up --non-interactive $child_branch $parent_branch
_do svnversion $parent_branch > $NEW_VERSION_F
new_version=$(cat $NEW_VERSION_F)

# A tricky way to ensure that this is indeed a valid number.
: $(( old_version += 0 ))
[ $old_version -gt 0 ]

if [ $new_version -eq $old_version ]
then
	echo "${0##*/}: INFO: New and old version are the same; nothing to do."
	exit 0
elif [ $new_version -lt $old_version ]
then
	echo "${0##*/}: ERROR: New version older than old version?!?!"
	exit 1
fi

child_branch_url=$(svn info "$child_branch" | awk '$1 == "URL:" { print $NF }')
child_branch_rroot=$(svn info "$child_branch" | awk '/^Repository Root:/ { print $NF }')
child_branch_relroot=$(echo $child_branch_url | sed -e "s,$child_branch_rroot/,,g")

set +e

failed_a_merge=false
i=$old_version
while [ $i -le $new_version ]
do
	_do svn log --incremental -r$i $parent_branch > revlog
	if [ $? -eq 0 -a -s revlog ]
	then

		do_not_merge=false
		if $honor_do_not_merge
		then
			if grep -q '^Do-Not-Merge: ' revlog
			then
				do_not_merge=true
			else
				set -x
				dnm_branches=$(sed -ne 's/^Do-Not-Merge (\(.*\)):\(.*\)/\1/p' revlog)
				for dnm_branch in $(echo "$dnm_branches" | sed -e 's/,/ /g')
				do
					echo "$child_branch_relroot" | grep -q "$dnm_branch\$"
					if [ $? -eq 0 ]
					then
						do_not_merge=true
						break
					fi
				done
				set +x
			fi
		fi
		if $do_not_merge
		then
			echo "Not merging r$i"
		else
			failed_merge=false

			# svn is stupid. Exit codes people!
			_do svn merge -c $i --dry-run $parent_branch $child_branch > merge-log
			if awk 'BEGIN { ec=1 } $1 == "C" || $2 == "C" { ec=0 } END { exit ec }' merge-log
			then
				failed_merge=true
			else
				_do svn merge --non-interactive -c $i \
				    $parent_branch $child_branch > merge-log
				j=0
				(
				 echo "Automerging change r$i from $parent_branch to $child_branch"
				 cat revlog
				) > commit
				if ! $fake_commit
				then
					while [ -n "$(_do svn status $child_branch | awk '$1 != "?"')" -a $j -lt 5 ]
					do
						_do svn ci --non-interactive \
						           -F commit $child_branch
						: $(( j += 1 ))
					done
				fi
				clean_svn
				if [ $j -eq 5 ]
				then
					failed_merge=true
				fi
				_do svn up --non-interactive $child_branch
			fi
			if $failed_merge
			then
				echo "${0##*/}: WARNING: couldn't automerge r$i -->"
				cat merge-log
				failed_a_merge=true
			fi
			rm merge-log
		fi
	elif [ -s revlog ]
	then
		echo "Failed to get log for r$i"
		cat revlog
	fi
	: $(( i += 1 ))
done
if $fake_commit
then
	exit
fi
mv $NEW_VERSION_F $OLD_VERSION_F
if $failed_a_merge
then
	exit 1
else
	exit 0
fi
