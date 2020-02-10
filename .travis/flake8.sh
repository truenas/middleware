#!/bin/sh

set -x

# Run pep8 on all .py files in all subfolders
# We must ignore E402 module level import not at top of file
# because of use case sys.path.append('..'); import <module>

tmpafter=$(mktemp)
find src -name \*.py -exec flake8 --ignore=E402,E501,W504 {} + | egrep -v "alembic/versions/|usr/local/share/pysnmp/mibs/" > $tmpafter
num_errors_after=`cat $tmpafter | wc -l`
echo $num_errors_after

if [ "${TRAVIS_PULL_REQUEST}" = "false" ]; then
git checkout HEAD~
else
git remote set-branches origin ${TRAVIS_BRANCH}
git fetch --depth 1 origin ${TRAVIS_BRANCH}
git checkout ${TRAVIS_BRANCH}
fi

tmpbefore=$(mktemp)
find src -name \*.py -exec flake8 --ignore=E402,E501,W504 {} + | egrep -v "alembic/versions/|usr/local/share/pysnmp/mibs/" > $tmpbefore
num_errors_before=`cat $tmpbefore | wc -l`
echo $num_errors_before


if [ $num_errors_after -gt $num_errors_before ]; then
	echo "New Flake8 errors were introduced:"
	diff -u $tmpbefore $tmpafter
	exit 1
fi

