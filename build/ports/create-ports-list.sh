#!/bin/sh
#

umask 022
cd "$(dirname "$0")/../.."
TOP="$(pwd)"
. build/nano_env

PORTSLIST=${NANO_OBJ}/poudriere/etc/ports.txt
MAKECONF=${NANO_OBJ}/poudriere/etc/make.conf
PORTOPTIONS=${NANO_OBJ}/poudriere/etc/poudriere.d/options

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
            mkdir -p ${PORTOPTIONS}/${PORT_UND} 
            rm -f ${PORTOPTIONS}/${PORT_UND}/options 
        else
            echo "$var" >> ${PORTOPTIONS}/${PORT_UND}/options 
        fi
    done
}

add_port_debug()
{
    add_port $* WITH_DEBUG=yes
}

mkdir -p $(dirname ${PORTSLIST})
mkdir -p ${PORTOPTIONS}
rm -f ${PORTSLIST}
rm -f ${MAKECONF}

. ${AVATAR_ROOT}/nanobsd/os-ports

