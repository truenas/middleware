#!/bin/sh

set -x

# Run pep8 on all .py files in all subfolders
# We must ignore E402 module level import not at top of file
# because of use case sys.path.append('..'); import <module>
branch=$(git rev-parse --abbrev-ref HEAD)
git checkout ${branch}~

tmpbefore=$(mktemp)
find gui -name \*.py -exec pep8 --ignore=E402,E501 {} + | grep -v "migrations/" > $tmpbefore
num_errors_before=`cat $tmpbefore | wc -l`
echo $num_errors_before

git checkout $branch

tmpafter=$(mktemp)
find gui -name \*.py -exec pep8 --ignore=E402,E501 {} + | grep -v "migrations/" > $tmpafter
num_errors_after=`cat $tmpafter | wc -l`
echo $num_errors_after

if [ $num_errors_after -gt $num_errors_before ]; then
	echo "New PEP8 errors were introduced:"
	diff -u $tmpbefore $tmpafter
	exit 1
fi

