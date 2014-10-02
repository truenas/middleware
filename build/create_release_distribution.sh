#!/bin/sh
#
# Create a tarball at the top of the tree for easy upload/extract to sourceforge
# directory format.
#

# Creating a json generating function
create_json()
{
  local filename=${1}
  local archbit=${2}
  local ftype=${3}
  local hash=${4}
  local url="http://download.freenas.org/nightlies/$(echo ${VERSION} | sed 's/ *-.*//')/$(echo ${VERSION} | sed -n -e 's/^.*-//p')/${BUILD_TIMESTAMP}/${archbit}/${NANO_NAME%-*}-${archbit}.${ftype}"
  
  cat<<-__EOF__>>${filename}.json
{
    "name": "${NANO_LABEL}",
    "version": "${VERSION}",
    "arch": "${archbit}",
    "install_type": "${ftype}",
    "hash": "${hash}",
    "date": "${BUILD_TIMESTAMP}",
    "url": "${url}"
}
__EOF__

}

cd "$(dirname "$0")/.."
TOP="$(pwd)"

. build/nano_env
. build/functions.sh

OBJ=objs

STAGEDIR="${NANO_LABEL}-${VERSION}-${BUILD_TIMESTAMP}"
rm -rf "${TOP}/${OBJ}/${STAGEDIR}"
set -x
set -e
mkdir -p "${TOP}/${OBJ}/${STAGEDIR}"

arch=x64
mapped_arch=amd64
mkdir -p ${TOP}/${OBJ}/${STAGEDIR}/${arch}
for ext in GUI_Upgrade.txz iso; do
	tfile=${TOP}/${OBJ}/os-base/$mapped_arch/${NANO_NAME%-*}-${arch}.${ext}
	if [ -f ${tfile} ]; then
		ln ${tfile} ${TOP}/${OBJ}/${STAGEDIR}/${arch}
		ln ${tfile}.sha256.txt ${TOP}/${OBJ}/${STAGEDIR}/${arch}
		create_json ${TOP}/${OBJ}/${STAGEDIR}/${arch}/${NANO_NAME%-*}-${arch}.${ext} ${arch} ${ext} $(cat ${tfile}.sha256.txt | sed -n -e 's/^.*= //p') 
	fi
done
