#!/bin/sh
# Helper script to convert old PBI module format to new 9.x format

fix_scripts() {
	osct="${1}"
	nsct="${2}"
	echo "#!/bin/sh" >${nsct}
	cat "${osct}" | sed 's|/Programs/${PROGDIR}|${PBI_PROGDIRPATH}|g' \
	| sed 's|/Programs/$PROGDIR|${PBI_PROGDIRPATH}|g' \
	| sed 's|${PROGDIR}|${PBI_PROGDIRPATH}|g' \
	| sed 's|$PROGDIR|${PBI_PROGDIRPATH}|g' \
	| sed 's|${PBIDIR}|${PBI_PROGDIRPATH}|g' \
	| sed 's|$PBIDIR|${PBI_PROGDIRPATH}|g' \
	| sed 's|/Programs/rc.d|${PBI_RCDIR}|g' \
	| sed 's|/Programs/etc|${SYS_LOCALBASE}/etc|g' \
	| sed 's|\.sbin|${PBI_FAKEBINDIR}|g' \
	| grep -v "^#" \
	| grep -v "LAUNCHCLOSE" \
	| grep -v "/Programs/bin" \
	| grep -v "/PCBSD/Services/" \
	| grep -v "kdialog" \
	 >>"${nsct}"
	_ce=`cat "${nsct}" | grep -v "^#" | sed '/^$/d'`
	if [ -z "$_ce" ] ; then rm "${nsct}" ; fi
}

odir="${1}"
if [ ! -z "$2" ]; then
	ndir="${2}"
else
	ndir="${1}.new"
fi
if [ ! -e "${odir}/pbi.conf" ] ; then
	echo "Invalid module dir!"
	exit 1
fi

if [ -d "${ndir}" ] ; then rm -rf "${ndir}" ; fi
mkdir -p "${ndir}"
mkdir "${ndir}/scripts"
mkdir "${ndir}/xdg-desktop"
mkdir "${ndir}/xdg-menu"
mkdir "${ndir}/xdg-mime"

# Start by moving obvious files over
if [ -d "${odir}/overlay-dir" ] ; then
  mkdir "${ndir}/resources"
  tar cvf - --exclude .svn -C ${odir}/overlay-dir . 2>/dev/null | tar xvf - -C ${ndir}/resources 2>/dev/null
fi

if [ -e "${ndir}/resources/LICENSE" ] ; then
  mv ${ndir}/resources/LICENSE ${ndir}/resources/
fi
if [ -e "${ndir}/resources/PBI.SetupScript.sh" ] ; then
  fix_scripts "${ndir}/resources/PBI.SetupScript.sh" "${ndir}/scripts/post-install.sh"
  rm "${ndir}/resources/PBI.SetupScript.sh"
fi
if [ -e "${ndir}/resources/PBI.RemoveScript.sh" ] ; then
  fix_scripts "${ndir}/resources/PBI.RemoveScript.sh" "${ndir}/scripts/pre-remove.sh"
  rm "${ndir}/resources/PBI.RemoveScript.sh"
fi
if [ -e "${ndir}/resources/PBI.FirstRun.sh" ] ; then
  fix_scripts "${ndir}/resources/PBI.FirstRun.sh" "${ndir}/scripts/pre-install.sh"
  rm "${ndir}/resources/PBI.FirstRun.sh"
fi
if [ -e "${odir}/build.sh" ] ; then
  fix_scripts "${odir}/build.sh" "${ndir}/scripts/post-portmake.sh"
fi
if [ -e "${odir}/preportmake.sh" ] ; then
  fix_scripts "${odir}/preportmake.sh" "${ndir}/scripts/pre-portmake.sh"
fi
if [ -e "${ndir}/resources/header.png" ] ; then
  mv ${ndir}/resources/header.png ${ndir}/resources/gui_banner.png
fi
if [ -e "${ndir}/resources/leftside.png" ] ; then
  mv ${ndir}/resources/leftside.png ${ndir}/resources/gui_sidebanner.png
fi
if [ -e "${ndir}/resources/PBI.UpdateURL.sh" ] ; then
  rm ${ndir}/resources/PBI.UpdateURL.sh
fi
if [ -d "${ndir}/resources/autolibs" ] ; then
  rm -rf ${ndir}/resources/autolibs
fi
if [ -d "${ndir}/resources/lib" ] ; then
  rm -rf ${ndir}/resources/lib
fi

# Delete empty dirs
find ${ndir}/resources -depth -empty -type d -exec rmdir {} \;


# Update the pbi.conf file
. ${odir}/pbi.conf

echo "#!/bin/sh
# PBI Build Configuration
# Place over-rides and settings here
#
# XDG Desktop Menu Spec:
# http://standards.freedesktop.org/menu-spec/menu-spec-1.0.html
##############################################################################
" >${ndir}/pbi.conf

expts=""
if [ ! -z "${PROGNAME}" ] ; then
  echo "# Program Name
PBI_PROGNAME=\"${PROGNAME}\"" >>${ndir}/pbi.conf
  echo " " >>${ndir}/pbi.conf
  expts="PBI_PROGNAME"  
fi
if [ ! -z "${PROGWEB}" ] ; then
  echo "# Program Website
PBI_PROGWEB=\"${PROGWEB}\"" >>${ndir}/pbi.conf
  echo " " >>${ndir}/pbi.conf
  expts="${expts} PBI_PROGWEB"  
fi
if [ ! -z "${PROGAUTHOR}" ] ; then
  echo "# Program Author / Vendor
PBI_PROGAUTHOR=\"${PROGAUTHOR}\"" >>${ndir}/pbi.conf
  echo " " >>${ndir}/pbi.conf
  expts="${expts} PBI_PROGAUTHOR"  
fi
if [ ! -z "${PROGICON}" ] ; then
  echo "# Default Icon (Relative to %%PBI_APPDIR%% or resources/)
PBI_PROGICON=\"${PROGICON}\"" >>${ndir}/pbi.conf
  echo " " >>${ndir}/pbi.conf
  expts="${expts} PBI_PROGICON"  
fi
if [ ! -z "${PBIPORT}" ] ; then
  # Fixed PBIPORT
  fPort=`echo $PBIPORT | sed 's|/usr/ports/||g'`
  echo "# The target port we are building
PBI_MAKEPORT=\"${fPort}\"" >>${ndir}/pbi.conf
  echo " " >>${ndir}/pbi.conf
  expts="${expts} PBI_MAKEPORT"  
fi
if [ ! -z "${MAKEOPTS}" ] ; then
  echo "# Additional options for make.conf
PBI_MAKEOPTS=\"${MAKEOPTS}\"" >>${ndir}/pbi.conf
  echo " " >>${ndir}/pbi.conf
  expts="${expts} PBI_MAKEOPTS"  
fi
if [ ! -z "${OTHERPORT}" ] ; then
  OP="`echo ${OTHERPORT} | sed 's|/usr/ports/||g'`"
  echo "# Ports to build before / after
PBI_MKPORTBEFORE=\"\"
PBI_MKPORTAFTER=\"${OP}\"" >>${ndir}/pbi.conf
  echo " " >>${ndir}/pbi.conf
  expts="${expts} PBI_MKPORTBEFORE PBI_MKPORTAFTER"  
fi

echo '# Files to be Sym-Linked into the default LOCALBASE
# One per-line, relative to %%PBI_APPDIR%% and LOCALBASE
# Defaults to keeping any existing files in LOCALBASE
# Use action 'binary' for binaries that need wrapper functionality

# TARGET                LINK IN LOCALBASE       ACTION
#etc/rc.d/servfoo       etc/rc.d/servfoo        keep
#include/libfoo.h       include/libfoo.h        replace
#bin/appfoo             bin/appfoo              binary,nocrash
#bin/appfoo2            bin/appfoo-test         binary
' > ${ndir}/external-links

# Now check kmenu-dir for desktop entries
if [ -d "${odir}/kmenu-dir" ] ; then
	for i in `ls -A ${odir}/kmenu-dir`
	do
		if [ "$i" = ".svn" ] ; then continue ; fi
		i="${odir}/kmenu-dir/${i}"
		app="" ; icon="" ; desc=""; nodesk=""; nomenu=""; nocrash=""; runroot=""
		runshell=""; notify=""; link=""; weblink=""; cat=""; nc=""

		app="`cat ${i} | grep 'ExePath: ' | sed 's|ExePath: ||g'`"
		icon="`cat ${i} | grep 'ExeIcon: ' | sed 's|ExeIcon: ||g'`"
		desc="`cat ${i} | grep 'ExeDescr: ' | sed 's|ExeDescr: ||g'`"
		nodesk="`cat ${i} | grep 'ExeNoDesktop: ' | sed 's|ExeNoDesktop: ||g'`"
		nomenu="`cat ${i} | grep 'ExeNoMenu: ' | sed 's|ExeNoMenu: ||g'`"
		nocrash="`cat ${i} | grep 'ExeNoCrashHandler: ' | sed 's|ExeNoCrashHandler: ||g'`"
		runroot="`cat ${i} | grep 'ExeRunRoot: ' | sed 's|ExeRunRoot: ||g'`"
		runshell="`cat ${i} | grep 'ExeRunShell: ' | sed 's|ExeRunShell: ||g'`"
		notify="`cat ${i} | grep 'ExeNotify: ' | sed 's|ExeNotify: ||g'`"
		link="`cat ${i} | grep 'ExeLink: ' | sed 's|ExeLink: ||g'`"
		weblink="`cat ${i} | grep 'ExeWebLink: ' | sed 's|ExeWebLink: ||g'`"
		cat="`cat ${i} | grep 'ExeKdeCat: ' | sed 's|ExeKdeCat: ||g'`"
	 	bname=`basename $app`

		if [ -z "$saved" ] ; then
			saved="$bname"
		else
			saved="$saved $bname"
		fi

		if [ "$link" = "1" -o "$weblink" = "1" ] ; then continue ; fi

		if [ "$notify" = "1" ] ; then 
			ntf="true"
		else
			ntf="false"
		fi
		if [ "$runroot" = "1" ] ; then 
			rr="X-KDE-SubstituteUID=true
X-KDE-Username=root"
		else
			rr=""
		fi
		if [ "$runshell" = "1" ] ; then 
			tt="Terminal=true
TerminalOptions="
		else
			tt=""
		fi

		# Convert to correct CAT
		if [ "$ncat" = "Internet" ] ; then
			ncat="Network"
		fi
		if [ "$ncat" = "Utilities" ] ; then
			ncat="Utility"
		fi
		ncat="`echo $cat | sed 's|/|;|g'`;"	

	 	# Create the menu .desktop file now
		if [ "$nomenu" = "1" ] ; then
			ndis="NoDisplay=true"
		else
			ndis=""
		fi

		echo -e "#!/usr/bin/env xdg-open
[Desktop Entry]
Value=1.0
Type=Application
Name=${desc}
GenericName=${desc}
Exec=%%PBI_EXEDIR%%/${bname}
Path=%%PBI_APPDIR%%
Icon=%%PBI_APPDIR%%/${icon}
StartupNotify=${ntf}
$ndis
$rr
$tt
Categories=$ncat" > ${ndir}/xdg-menu/${bname}.desktop
		sed '/^$/d' ${ndir}/xdg-menu/${bname}.desktop > ${ndir}/xdg-menu/${bname}.desktop.new
		mv ${ndir}/xdg-menu/${bname}.desktop.new ${ndir}/xdg-menu/${bname}.desktop 

	 	# Create the desktop .desktop file now
		if [ "$nodesk" != "1" ] ; then
	 	bname=`basename $app`
		echo -e "#!/usr/bin/env xdg-open
[Desktop Entry]
Value=1.0
Type=Application
Name=${desc}
GenericName=${desc}
Exec=%%PBI_EXEDIR%%/${bname}
Path=%%PBI_APPDIR%%
Icon=%%PBI_APPDIR%%/${icon}
StartupNotify=${ntf}
$rr
$tt" > ${ndir}/xdg-desktop/${bname}.desktop
		sed '/^$/d' ${ndir}/xdg-desktop/${bname}.desktop > ${ndir}/xdg-desktop/${bname}.desktop.new
		mv ${ndir}/xdg-desktop/${bname}.desktop.new ${ndir}/xdg-desktop/${bname}.desktop
		fi # End of desktop check
		
	done
fi

# Now setup mime types
if [ -d "${odir}/mime-dir" ] ; then
	for i in `ls -A ${odir}/mime-dir`
	do
		if [ "$i" = ".svn" ] ; then continue ; fi
		i="${odir}/mime-dir/${i}"
		ext="" ; icon="" ; prog=""

		ext="`cat ${i} | grep 'MimeExt: ' | sed 's|MimeExt: ||g' | sed 's|;||g'`"
		icon="`cat ${i} | grep 'MimeIcon: ' | sed 's|MimeIcon: ||g'`"
		prog="`cat ${i} | grep 'MimeProg: ' | sed 's|MimeProg: ||g' | sed 's| ||g'`"

		# Get the bname of the program this mime-type is associated with
		count=0
		bname=""
		for j in $saved
		do
			if [ "$count" = "$prog" ] ; then bname="$j" ; break ; fi
			count="`expr $count + 1`"
		done
		if [ -z "$bname" ] ; then echo "Missing mime bname!: $prog - $ext" ; continue ; fi

		comment="`cat ${ndir}/xdg-menu/${bname}.desktop | grep "GenericName" | cut -d '=' -f 2-10`"

		# Add the mime entry to the original .desktop file
		echo "MimeType=application/x-${bname}" >> ${ndir}/xdg-menu/${bname}.desktop
		echo "<?xml version=\"1.0\"?>
<mime-info xmlns='http://www.freedesktop.org/standards/shared-mime-info'>
  <mime-type type=\"application/x-${bname}\">
    <comment>${comment} File</comment>" >${ndir}/xdg-mime/${bname}-xdg.xml
		for j in $ext
		do	
   			echo "    <glob weight=\"100\" pattern=\"${j}\"/>" >> ${ndir}/xdg-mime/${bname}-xdg.xml
		done
echo " </mime-type>
</mime-info>" >>${ndir}/xdg-mime/${bname}-xdg.xml

		# See if we have icon as well
		if [ -e "${ndir}/resources/${icon}" ] ; then
			cp "${ndir}/resources/${icon}" "${ndir}/xdg-mime/${bname}-xdg.png"
		fi


	done

fi

echo "export $expts" >> ${ndir}/pbi.conf
