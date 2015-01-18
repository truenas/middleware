#!/bin/sh
#
# Create a tarball at the top of the tree for easy upload/extract to sourceforge
# directory format.
#

# This is to create the intermediatary JSON blocks for the various
# different filetypes and so on. It takes 5 params as the input:
# 1. JSON File to write this to
# 2. Filename
# 3. Filetype (iso, usb, ...)
# 4. Hash of the above file
# 5. URL of the file on download.freenas.org
json_block()
{
  cat<<-__EOF__>>${1}
            {
                "filename": "${2}",
                "type": "${3}",
                "hash": "${4}",
                "url": "${5}/${2}"
            },
__EOF__
}

# Creating a json generating function
# It takes 2 params as the input: 
# 1. The Parent path to the build (This is the folder which will contain the x86/x64 dirs)
# 2. The Top Freenas Directory (this is for the Release Notes)
create_json()
{
  local dpath=${1}
  local buildtype=$(echo ${VERSION} | sed -n -e 's/^.*-//p') # Is it RELEASE or nightly milestones
  local arch # The architecture (x64 or x86)
  #local Archbit # The above sans the "x"
  local ftype # This describes the type (iso, usb, GUI_Upgrade.txz or img)
  local hash # The Hash of the file
  local filename # The full name of the file we are dealing with
  local json_file="$dpath/CHECKSUMS.json" #This is the location of the resulting JSON file
  
  if [ $buildtype = "RELEASE" ];
  then
      local url="http://download.freenas.org/$(echo ${VERSION} | sed 's/ *-.*//')/RELEASE/"
  else
      local url="http://download.freenas.org/nightlies/$(echo ${VERSION} | sed 's/ *-.*//')"\
"/$(echo ${VERSION} | sed -n -e 's/^.*-//p')/${BUILD_TIMESTAMP}/"
  fi  
  cat<<-__EOF__>>${json_file}
{
    "name": "${NANO_LABEL}",
    "version": "$(echo ${VERSION} | sed 's/ *-.*//')",
    "build_type": "$buildtype",
    "date": "${BUILD_TIMESTAMP}",
    "aux_files": [
        {
            "filename": "ReleaseNotes",
            "hash": "$(sha256 ${2}/ReleaseNotes | sed -n -e 's/^.*= //p')"
        },
        {
            "filename": "MANIFEST",
            "hash": "$(sha256 $dpath/MANIFEST | sed -n -e 's/^.*= //p')"
        },
        {
            "filename": "README",
            "hash": "$(sha256 $dpath/README | sed -n -e 's/^.*= //p')"
        }
    ],
    "arch": {
__EOF__

  local archdirs=$(find $dpath -type d -mindepth 1 -maxdepth 1)
  for x in $archdirs; do
   #archbit=$(basename $x | cut -c 2-)
   arch=$(basename $x)
   iso=$x/${NANO_NAME}.iso
   usb=$x/${NANO_NAME}.usb
   gui_upgrade=$x/${NANO_NAME}.GUI_Upgrade.txz
   img=$x/${NANO_NAME}.img
   
   cat<<-__EOF__>>${json_file}
        "${arch}": [
__EOF__
   
   if [ ! -z "$iso" ]; then
      filename=$(basename $iso)
      hash=$(cat ${iso}.sha256.txt | sed -n -e 's/^.*= //p') 
      json_block ${json_file} ${filename} "iso" ${hash} ${url}${arch}
   fi
   
   if [ ! -z "$usb" ]; then
       filename=$(basename $usb)
       hash=$(cat ${usb}.sha256.txt | sed -n -e 's/^.*= //p') 
       json_block ${json_file} ${filename} "usb" ${hash} ${url}${arch}
   fi
   
   if [ ! -z "$gui_upgrade" ]; then
       filename=$(basename $gui_upgrade)
       hash=$(cat ${gui_upgrade}.sha256.txt | sed -n -e 's/^.*= //p') 
       json_block ${json_file} ${filename} "gui_upgrade" ${hash} ${url}${arch}
   fi
   
   if [ ! -z "$img" ]; then
       filename=$(basename $img)
       hash=$(cat ${img}.sha256.txt | sed -n -e 's/^.*= //p') 
       json_block ${json_file} ${filename} "img" ${hash} ${url}${arch}
   fi
   
   # Removing the last comma (this is hacky hack)
   sed -i "" '$s/,$//' ${json_file}
   
   cat<<-__EOF__>>${json_file} 
        ],
__EOF__

  done
  
  # Removing the last comma (this is hacky hack)
  sed -i "" '$s/,$//' ${json_file}
  
  cat<<-__EOF__>>${json_file}
    }
}
__EOF__

}


cd "$(dirname "$0")/.."
TOP="$(pwd)"

. build/nano_env
. build/functions.sh

set -x
set -e

OBJ=objs
STAGEDIR="${NANO_LABEL}-${VERSION}-${BUILD_TIMESTAMP}"
TARGET="${TOP}/${OBJ}/${STAGEDIR}/x64"
mkdir -p "${TARGET}"

for ext in GUI_Upgrade.txz iso; do
	tfile=${TOP}/${OBJ}/os-base/amd64/${NANO_NAME}.${ext}
	if [ -f ${tfile} ]; then
		mv ${tfile} "${TARGET}"
		mv ${tfile}.sha256.txt "${TARGET}"
	else
		echo "** ERROR: Unable to find ${tfile}"
	fi
done

sed -e "s/VERSION/${VERSION}/" -e "s/BUILD_TIMESTAMP/${BUILD_TIMESTAMP}/" < ${TOP}/build/README > "${TARGET}/../README"
cp ${TOP}/FreeBSD/repo-manifest "${TARGET}/../MANIFEST"

echo "Creating the JSON Checksums file..."
create_json ${TOP}/${OBJ}/${STAGEDIR} ${TOP} 
