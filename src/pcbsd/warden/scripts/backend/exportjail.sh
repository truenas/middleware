#!/bin/sh
# Export a jail into a self-contained file for transport / backup
######################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

IP="$1"
OUTDIR="$2"

if [ -z "${IP}" ]
then
  echo "ERROR: No jail specified to chroot into!"
  exit 5
fi

if [ -z "${JDIR}" ]
then
  echo "ERROR: JDIR is unset!!!!"
  exit 5
fi

if [ ! -d "${JDIR}/${IP}" ]
then
  echo "ERROR: No jail located at $JDIR/$IP"
  exit 5
fi

set_warden_metadir

# First check if this jail is running, and stop it
${PROGDIR}/scripts/backend/checkstatus.sh "$IP"
if [ "$?" = "0" ]
then
  ${PROGDIR}/scripts/backend/stopjail.sh "$IP"
fi

# Now that the jail is stopped, lets make a large tbz file of it
cd ${JDIR}/${IP}

# Get the Hostname
HOST="`cat ${JMETADIR}/host`"


echo "Creating compressed archive of ${IP}... Please Wait..." >&1
tar cvJf "${WTMP}/${IP}.tlz" -C "${JDIR}/${IP}" . 2>${WTMP}/${IP}.files

cd ${WTMP}

LINES="`wc -l ${IP}.files | sed -e 's, ,,g' | cut -d '.' -f 1`"


# Finished, now make the header info
cd ${WTMP}
echo "[Warden file]
Ver: 1.0 
OS: `uname -r | cut -d '-' -f 1`
Files: $LINES
IP: ${IP}
HOST: ${HOST}
" >${WTMP}/${IP}.header

# Copy over jail extra meta-data
cp ${JMETADIR}/jail-* ${WTMP}/ 2>/dev/null

# Compress the header file
tar cvzf ${IP}.header.tgz ${IP}.header jail-* 2>/dev/null

# Create our spacer
echo "
___WARDEN_START___" > .spacer

# Make the .wdn file now
cat ${IP}.header.tgz .spacer ${IP}.tlz > ${IP}.wdn

# Remove the old files
rm ${IP}.header
rm ${IP}.files
rm ${IP}.tlz
rm .spacer
rm ${IP}.header.tgz

# Remove any extra jail meta-files from WTMP
for i in `ls ${JMETADIR}/jail-* 2>/dev/null`
do
  mFile=`basename $i`
  rm $mFile
done

if [ ! -z "${OUTDIR}" ]
then
  mkdir -p ${OUTDIR} 2>/dev/null
  mv ${IP}.wdn ${OUTDIR}/
  echo "Created ${IP}.wdn in ${OUTDIR}" >&1
else 
  echo "Created ${IP}.wdn in ${WTMP}" >&1
fi


exit 0

