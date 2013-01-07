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
  echo "ERROR: No jail specified to chroot into!"
  exit 5
fi

if [ -z "${JDIR}" ]
then
  echo "ERROR: JDIR is unset!!!!"
  exit 5
fi

JAILDIR="${JDIR}/${JAILNAME}"

if [ ! -d "${JAILDIR}" ]
then
  echo "ERROR: No jail located at ${JAILDIR}"
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
IP="`cat ${JMETADIR}/ip`"

get_ip_and_netmask "${IP}"
IP="${JIP}"
MASK="${JMASK}"

echo "Creating compressed archive of ${JAILNAME}... Please Wait..." >&1
tar cvJf "${WTMP}/${JAILNAME}.tlz" -C "${JAILDIR}" . 2>${WTMP}/${JAILNAME}.files

cd ${WTMP}

LINES="`wc -l ${JAILNAME}.files | sed -e 's, ,,g' | cut -d '.' -f 1`"

# Finished, now make the header info
cd ${WTMP}
echo "[Warden file]
Ver: 1.0 
OS: `uname -r | cut -d '-' -f 1`
Files: $LINES
IP: ${IP}/${MASK}
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
  echo "Created ${JAILNAME}.wdn in ${OUTDIR}" >&1
else 
  echo "Created ${JAILNAME}.wdn in ${WTMP}" >&1
fi

exit 0
