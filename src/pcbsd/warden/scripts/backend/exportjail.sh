#!/bin/sh
# Export a jail into a self-contained file for transport / backup
######################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

JAILNAME="$1"
OUTDIR="$2"

if [ -z "${JAILNAME}" ]
then
  warden_error "No jail specified to chroot into!"
  exit 5
fi

if [ -z "${JDIR}" ]
then
  warden_error "JDIR is unset!!!!"
  exit 5
fi

JAILDIR="${JDIR}/${JAILNAME}"

if [ ! -d "${JAILDIR}" ]
then
  warden_error "No jail located at ${JAILDIR}"
  exit 5
fi

set_warden_metadir

# First check if this jail is running, and stop it
${PROGDIR}/scripts/backend/checkstatus.sh "${JAILNAME}"
if [ "$?" = "0" ]
then
  ${PROGDIR}/scripts/backend/stopjail.sh "${JAILNAME}"
fi

# Now that the jail is stopped, lets make a large tbz file of it
cd ${JAILDIR}

# Get the Hostname
HOST="`cat ${JMETADIR}/host`"

IP4="`cat ${JMETADIR}/ipv4 2>/dev/null`"
IP6="`cat ${JMETADIR}/ipv6 2>/dev/null`"

get_ip_and_netmask "${IP4}"
IP4="${JIP}"
MASK4="${JMASK}"

get_ip_and_netmask "${IP6}"
IP6="${JIP}"
MASK6="${JMASK}"

warden_print "Creating compressed archive of ${JAILNAME}... Please Wait..."
tar cvJf "${WTMP}/${JAILNAME}.tlz" -C "${JAILDIR}" . 2>${WTMP}/${JAILNAME}.files

cd ${WTMP}

LINES="`wc -l ${JAILNAME}.files | sed -e 's, ,,g' | cut -d '.' -f 1`"

# Finished, now make the header info
cd ${WTMP}
echo "[Warden file]
Ver: 1.0 
OS: `uname -r | cut -d '-' -f 1`
Files: $LINES
IP4: ${IP4}/${MASK4}
IP6: ${IP6}/${MASK6}
HOST: ${HOST}
" >${WTMP}/${JAILNAME}.header

# Copy over jail extra meta-data
cp ${JMETADIR}/jail-* ${WTMP}/ 2>/dev/null

# Compress the header file
tar cvzf ${JAILNAME}.header.tgz ${JAILNAME}.header jail-* 2>/dev/null

# Create our spacer
echo "
___WARDEN_START___" > .spacer

# Make the .wdn file now
cat ${JAILNAME}.header.tgz .spacer ${JAILNAME}.tlz > ${JAILNAME}.wdn

# Remove the old files
rm ${JAILNAME}.header
rm ${JAILNAME}.files
rm ${JAILNAME}.tlz
rm .spacer
rm ${JAILNAME}.header.tgz

# Remove any extra jail meta-files from WTMP
for i in `ls ${JMETADIR}/jail-* 2>/dev/null`
do
  mFile=`basename $i`
  rm $mFile
done

if [ ! -z "${OUTDIR}" ]
then
  mkdir -p ${OUTDIR} 2>/dev/null
  mv ${JAILNAME}.wdn ${OUTDIR}/
  warden_print "Created ${JAILNAME}.wdn in ${OUTDIR}" 
else 
  warden_print "Created ${JAILNAME}.wdn in ${WTMP}"
fi

exit 0
