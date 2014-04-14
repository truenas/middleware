#!/bin/sh
#

umask 022
cd "$(dirname "$0")/../.."
TOP="$(pwd)"
. build/nano_env
. build/repos.sh

# XX: Uncomment following to test using poudriere to fetch
#     ports tree.
#poudriere -e ${NANO_OBJ}/poudriere/etc ports -c -p p -m git

# Create the metadata which tells poudriere where the checked
# out ports tree lives.  Use the checked out tree that the
# FreeNAS build uses.
PORTS_TREE=p
mkdir -p ${NANO_OBJ}/poudriere/etc/poudriere.d/ports/${PORTS_TREE}
echo "${GIT_PORTS_CHECKOUT_PATH}" > ${NANO_OBJ}/poudriere/etc/poudriere.d/ports/${PORTS_TREE}/mnt
echo "git" > ${NANO_OBJ}/poudriere/etc/poudriere.d/ports/${PORTS_TREE}/method

