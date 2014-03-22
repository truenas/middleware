#!/bin/sh
#

umask 022
cd "$(dirname "$0")/../.."
TOP="$(pwd)"
. build/nano_env
#. build/functions.sh

TMP=`mktemp -t nanopoud`

BUILDFILE=${NANO_OBJ}/poudriere.build.txt
MAKECONF=${NANO_OBJ}/poudriere.make.conf

rm -f ${BUILDFILE}
rm -f ${MAKECONF}

customize_cmd()
{
}

FlashDevice()

. nanobsd/os-base

add_port()
{
    local PORT
    local PORT_UND
    local var
   
    for var in "$@"; do
        if [ -z "$PORT" ]; then
            PORT=$var
            PORT_UND=$(echo $var|sed -e 's|/|_|g')
            echo $PORT >> $BUILDFILE
            
        else
            echo "${PORT_UND}_SET += ${var}" >> $MAKECONF
        fi
    done
}

add_port_debug()
{
    add_port $@
}

echo "" > ${TMP}
echo "NANO_PACKAGE_ONLY=0" >> ${TMP} 
echo "if true; then" >> ${TMP}
grep -A 25  add_port nanobsd/os-base   | sed -e 's/^\-\-//' >> ${TMP}
sed -i "" -e 's|add_port editors/vim-lite|if [ \"${DEBUG}\" = \"1\" ]; then add_port editors/vim-lite|' ${TMP}
echo "fi" >> ${TMP}
echo "" >> ${TMP}

. ${TMP}

rm -f ${TMP}
