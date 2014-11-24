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

# Download the PC-BSD ports tree
if [ -d "${GIT_PCBSD_CHECKOUT_PATH}" ] ; then
   # We have a tree, just update it
   cd ${GIT_PCBSD_CHECKOUT_PATH} && git pull
else
  # Fresh checkout
  git clone -b ${GIT_PCBSD_BRANCH} ${GIT_PCBSD_REPO} ${GIT_PCBSD_CHECKOUT_PATH}
  if [ $? -ne 0 ] ; then
     echo "Failed checking out PC-BSD sources from github..."
     exit 1
  fi
fi

# Figure out where to place PCBSD generated distfiles
PCBSD_DISTFILES_CACHE="${NANO_OBJ}/ports/distfiles"
if [ -n "$PORTS_DISTFILES_CACHE" -a -d "$PORTS_DISTFILES_CACHE" ] ; then
   PCBSD_DISTFILES_CACHE="$PORTS_DISTFILES_CACHE"
fi
if [ ! -d "$PCBSD_DISTFILES_CACHE" ] ; then
  mkdir -p ${PCBSD_DISTFILES_CACHE}
fi

# Merge the PC-BSD ports into the FreeNAS tree
cd ${GIT_PCBSD_CHECKOUT_PATH} && ./mkports.sh ${GIT_PORTS_CHECKOUT_PATH} ${PCBSD_DISTFILES_CACHE}

# Create the metadata which tells poudriere where the checked
# out ports tree lives.  Use the checked out tree that the
# FreeNAS build uses.
PORTS_TREE=p
mkdir -p ${NANO_OBJ}/poudriere/etc/poudriere.d/ports/${PORTS_TREE}
echo "${GIT_PORTS_CHECKOUT_PATH}" > ${NANO_OBJ}/poudriere/etc/poudriere.d/ports/${PORTS_TREE}/mnt
echo "git" > ${NANO_OBJ}/poudriere/etc/poudriere.d/ports/${PORTS_TREE}/method

