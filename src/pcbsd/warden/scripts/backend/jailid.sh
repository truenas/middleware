#!/bin/sh

. /usr/local/share/warden/scripts/backend/functions.sh

__set_unique_id()
{
   local jdir="${1}"
   local jmetadir="${2}"

   local meta_id=0
   local lockfile="/var/tmp/.idlck"

   meta_id="$(get_next_id "${jdir}")"
   echo "${meta_id}" > "${jmetadir}/id"

   return $?
}

__set_unique_id "${1}" "${2}"
exit $?
