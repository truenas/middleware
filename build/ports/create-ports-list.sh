#!/bin/sh
#

umask 022
cd "$(dirname "$0")/../.."
TOP="$(pwd)"
. build/nano_env

PORTSLIST=${NANO_OBJ}/poudriere/etc/ports.txt
MAKECONF=${NANO_OBJ}/poudriere/etc/make.conf

# Take the old add_port invocations from
# the nanobsd script, and create input files
# which can be passed to poudriere.

add_port()
{
    local PORT
    local PORT_UND
    local var
   
    for var in "$@"; do
        if [ -z "$PORT" ]; then
            PORT=$var
            PORT_UND=$(echo $var|sed -e 's|/|_|g')
            echo $PORT >> $PORTSLIST
            
        else
            echo "${PORT_UND}_SET += ${var}" >> $MAKECONF
        fi
    done
}

add_port_debug()
{
    add_port $@
}

mkdir -p $(dirname ${PORTSLIST})
rm -f ${PORTSLIST}
rm -f ${MAKECONF}

. ${AVATAR_ROOT}/nanobsd/os-ports

