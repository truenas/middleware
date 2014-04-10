############################################################ CONFIGURATION

SR		= sudo
MNT		= mnt
STATIC_CONF	= etc/static.conf
MFSSIZE		= 6000
MFSINODE	= 8000
ARCHIVE		= netboot

############################################################ MAIN TARGETS

all: remake

usage:
	@if ! [ -f "$(STATIC_CONF)" ] || ! . "$(STATIC_CONF)"; then	\
	 	echo "WARNING: could not open $(STATIC_CONF)";		\
	 else								\
	 	[ "$$STATIC_BASE" ] || echo "WARNING: STATIC_BASE"	\
	 		"not defined in $(STATIC_CONF)" >&2;		\
	 	[ "$$OUTPUT" ] || echo "WARNING: OUTPUT"		\
	 		"not defined in $(STATIC_CONF)" >&2;		\
	 fi;								\
	 OUTPUT="$${OUTPUT:-OUTPUT}";					\
	 STATIC_BASE="$${STATIC_BASE:-STATIC_BASE}";			\
	 echo "Targets:";						\
	 echo "	all/default:	same as \`remake'";			\
	 echo "	almostclean:	Delete only files in static/";		\
	 echo "	archive:	Make \`distclean' archive in \`../'";	\
	 echo "	clean:		Delete $$OUTPUT and static/";		\
	 echo "	close:		Close $$OUTPUT";			\
	 echo "	copy:		Copy src into opened image";		\
	 echo "	distclean:	Delete $$OUTPUT, static/, and configs";	\
	 echo "	from_dep:	Re-make from stored dependencies";	\
	 echo "	help/usage:	Print this text and exit";		\
	 echo "	install:	Copy $$OUTPUT to $$STATIC_BASE/boot";	\
	 echo "	open:		Open $$OUTPUT";				\
	 echo "	remake:		Open, re-copy src, and close";		\
	 echo "	update_mtree:	Update mtree of clean static/";		\
	 echo "	update_static:	Update static/ binaries";		\
	 echo "	mtree:		Create basic static directories";	\
	 echo

help: usage

update_mtree:
	@if [ ! -d "static" ]; then				\
	 	cmd="$(SR) mkdir -p static";			\
	 	echo "$$cmd"; eval "$$cmd" || exit $$?;		\
	 fi;							\
	 if [ "$$( find static -type f )" ]; then		\
	 	echo "ERROR: run \`$(MAKE) clean' first" >&2;	\
	 	exit 1;						\
	 fi;							\
	 cmd="echo '# \$$''Header''\$$' > etc/static.mtree";	\
	 echo "$$cmd"; eval "$$cmd" || exit $$?;		\
	 cmd="cd static && $(SR) mtree -c -i -p .";		\
	 cmd="$$cmd -k gname,mode,uname,link,type";		\
	 cmd="$$cmd >> ../etc/static.mtree";			\
	 echo "$$cmd"; eval "$$cmd"

mtree:
	@if [ ! -d "static" ]; then			\
	 	cmd="$(SR) mkdir -p static";		\
	 	echo "$$cmd"; eval "$$cmd" || exit $$?;	\
	 fi
	$(SR) mtree -eU -f etc/static.mtree -p static

stage0:
	@. "$(STATIC_CONF)" || exit $$?;				\
	 if [ ! -d "static" ]; then					\
	 	cmd="$(MAKE) mtree";					\
	 	echo "$$cmd"; eval "$$cmd" || exit $$?;			\
	 fi;								\
	 if [ ! "$$STATIC_BASE" ]; then					\
	 	echo "!!! STATIC_BASE not defined in"			\
	 	     "$(STATIC_CONF)" >&2; 				\
	 	exit 1;							\
	 fi;								\
	 echo ">>> Updating static/ with $$STATIC_BASE/:";		\
	 srcfile="$$STATIC_BASE/libexec/ld-elf.so.1";			\
	 $(SR) cp -f "$$srcfile" static/libexec/ || exit $$?;		\
	 echo -n "$${srcfile#$$STATIC_BASE} ";				\
	 echo " -> static/libexec/$${srcfile##*/}";			\
	 for file in							\
	 	arp               awk               cat			\
	 	chmod             chown             chroot		\
	 	cmp               cp                devfs		\
	 	dhclient          dhclient-script   find		\
	 	halt              hostname          ifconfig		\
	 	init              kenv              kldstat		\
	 	mdconfig          mkdir             mount		\
	 	mount_nfs         mount_smbfs       newfs		\
	 	printf            reboot            resolvconf		\
	 	rm                route             sed			\
	 	sh                sleep             stat		\
	 	tail              umount            xargs		\
	 ; do								\
	 	found=;							\
	 	for dir in bin sbin usr/bin usr/sbin; do		\
	 		srcfile="$$STATIC_BASE/$$dir/$$file";		\
	 		[ -f "$$srcfile" ] && found=1;			\
	 		[ "$$found" ] || continue;			\
	 		$(SR) cp -f "$$srcfile" static/stand/ ||	\
	 			exit $$?;				\
	 		echo -n "$${srcfile#$$STATIC_BASE}";		\
	 		echo " -> static/stand/$${srcfile##*/}";	\
	 		break;						\
	 	done;							\
	 	if [ ! "$$found" ]; then				\
	 		echo "$$file: No such file or directory" >&2;	\
	 		exit 1;						\
	 	fi;							\
	 done;								\
	 for lib in							\
	 	libbsdxml.so.4    libc.so.7         libedit.so.7	\
	 	libgeom.so.5      libjail.so.1      libkiconv.so.4	\
	 	libm.so.5         libncurses.so.8   libsbuf.so.6	\
	 	libsmb.so.4       libufs.so.6       libutil.so.9	\
	 ; do								\
	 	found=;							\
	 	for dir in lib usr/lib; do				\
	 		srcfile="$$STATIC_BASE/$$dir/$$lib";		\
	 		[ -f "$$srcfile" ] && found=1;			\
	 		[ "$$found" ] || continue;			\
	 		$(SR) cp -f "$$srcfile" static/lib/ ||		\
	 			exit $$?;				\
	 		echo -n "$${srcfile#$$STATIC_BASE}";		\
	 		echo " -> static/lib/$${srcfile##*/}";		\
	 		break;						\
	 	done;							\
	 	if [ ! "$$found" ]; then				\
	 		echo "$$lib: No such file or directory" >&2;	\
	 		exit 1;						\
	 	fi;							\
	 done;								\
	 for lib in libipx.so.5; do					\
	 	found=;							\
	 	for dir in lib usr/lib; do				\
	 		srcfile="$$STATIC_BASE/$$dir/$$lib";		\
	 		[ -f "$$srcfile" ] && found=1 break;		\
	 	done;							\
	 	if [ "$$found" ]; then					\
	 		$(SR) cp -f "$$srcfile" static/lib/ ||		\
	 			exit $$?;				\
	 		echo -n "$${srcfile#$$STATIC_BASE}";		\
	 		echo " -> static/lib/$${srcfile##*/}";		\
	 	fi;							\
	 done;								\
	 for file in devfs.conf netconfig services group; do		\
	 	srcfile="$$STATIC_BASE/etc/$$file";			\
	 	$(SR) cp -f "$$srcfile" static/etc/ || exit $$?;	\
	 	echo -n "$${srcfile#$$STATIC_BASE}";			\
	 	echo " -> static/etc/$${srcfile##*/}";			\
	 done;								\
	 srcfile="$$STATIC_BASE/etc/master.passwd";			\
	 $(SR) cp -f "$$srcfile" static/etc/ || exit $$?;		\
	 echo "$${srcfile#$$STATIC_BASE} -> static/etc/$${srcfile##*/}"

stage1: dep/mfsroot.gz
	@. "$(STATIC_CONF)" || exit $$?;				\
	 if [ ! "$$OUTPUT" ]; then					\
	 	echo "!!! OUTPUT not defined in $(STATIC_CONF)" >&2;	\
	 	exit 1;							\
	 fi;								\
	 cmd="cp -i dep/mfsroot.gz \"$$OUTPUT\"";			\
	 echo "$$cmd"; eval "$$cmd"

stage2:
	@. "$(STATIC_CONF)" || exit $$?;				\
	 if [ ! "$$OUTPUT" ]; then					\
	 	echo "!!! OUTPUT not defined in $(STATIC_CONF)" >&2;	\
	 	exit 1;							\
	 fi;								\
	 if [ ! -f "static/libexec/ld-elf.so.1" ]; then			\
	 	cmd="$(MAKE) update_static";				\
	 	echo "$$cmd"; eval "$$cmd" || exit $$?;			\
	 fi;								\
	 if [ ! -f "$$OUTPUT" ]; then					\
	 	cmd="$(MAKE) stage1";					\
	 	echo "$$cmd"; eval "$$cmd" || exit $$?;			\
	 fi;								\
	 cleanup=;							\
	 cmd="gunzip \"$$OUTPUT\"";					\
	 echo "$$cmd"; eval "$$cmd" || exit $$?;			\
	 cmd="mkdir -p \"$(MNT)\"";					\
	 echo "$$cmd"; eval "$$cmd" || exit $$?;			\
	 mfsroot="$${OUTPUT%.gz}";					\
	 cmd="$(SR) mdconfig -f \"$$mfsroot\"";				\
	 echo "$$cmd"; md=$$( eval "$$cmd" ) || exit $$?;		\
	 echo "$$md";							\
	 cleanup="$(SR) mdconfig -d -u $${md#md}; $$cleanup";		\
	 trap "$$cleanup" EXIT;						\
	 cmd="$(SR) mount /dev/$$md \"$(MNT)\"";			\
	 echo "$$cmd"; eval "$$cmd" || exit $$?;			\
	 trap - EXIT

stage3:
	mkdir -p src/netroot
	$(SR) cp version.inf $(MNT)/version.inf
	@: ====================================================== ;	\
	 cmd="( cd static && find . -type d -mindepth 1 ! -name CVS";	\
	 cmd="$$cmd -exec $(SR) mkdir -pv '../$(MNT)/{}' \\; )";	\
	 echo "$$cmd"; eval "$$cmd" || exit $$?;			\
	 cmd="( cd static && find . -type f ! -path '*/CVS/*'";		\
	 cmd="$$cmd ! -name .keep";					\
	 cmd="$$cmd -exec $(SR) cp -fv '{}' '../$(MNT)/{}' \\; )";	\
	 echo "$$cmd"; eval "$$cmd" || exit $$?;			\
	 cmd="( cd static && find . -type l";				\
	 cmd="$$cmd -exec $(SR) cp -RPfv '{}' '../$(MNT)/{}' \\; )";	\
	 echo "$$cmd"; eval "$$cmd"
	@: ====================================================== ;	\
	 cmd="( cd src && find . -type d -mindepth 1 ! -name CVS";	\
	 cmd="$$cmd -exec $(SR) mkdir -pv '../$(MNT)/{}' \\; )";	\
	 echo "$$cmd"; eval "$$cmd" || exit $$?;			\
	 cmd="( cd src && find . -type f ! -path '*/CVS/*'";		\
	 cmd="$$cmd ! -name .keep";					\
	 cmd="$$cmd -exec $(SR) cp -fv '{}' '../$(MNT)/{}' \\; )";	\
	 echo "$$cmd"; eval "$$cmd" || exit $$?;			\
	 cmd="( cd src && find . -type l";				\
	 cmd="$$cmd -exec $(SR) cp -RPfv '{}' '../$(MNT)/{}' \\; )";	\
	 echo "$$cmd"; eval "$$cmd"
	@: ====================================================== ;	\
	 cmd="( cd $(MNT) && $(SR) rm -f etc/pwd.db etc/spwd.db &&";	\
	 cmd="$$cmd $(SR) pwd_mkdb -i -d etc etc/master.passwd )";	\
	 echo "$$cmd"; eval "$$cmd"

stage4:
	[ ! -d "$(MNT)" ] || $(SR) umount $(MNT) || true
	[ ! -d "$(MNT)" ] || rmdir $(MNT)
	@. "$(STATIC_CONF)" || exit $$?;				\
	 if [ ! "$$OUTPUT" ]; then					\
	 	echo "!!! OUTPUT not defined in $(STATIC_CONF)" >&2;	\
	 	exit 1;							\
	 fi;								\
	 mfsroot="$${OUTPUT%.gz}";					\
	 for md in $$( $(SR) mdconfig -lv |				\
	 	awk -v pwd="$$( pwd )" -v mfsroot="$$mfsroot"		\
	 	'$$2 == "vnode" { md = $$1;				\
	 		sub("^[^[:space:]]+[[:space:]]+", "");		\
	 		sub("^[^[:space:]]+[[:space:]]+", "");		\
	 		sub("^[^[:space:]]+[[:space:]]+", "");		\
	 		if ($$0 == pwd "/" mfsroot) print md		\
	 	}' );							\
	 do								\
	 	cmd="$(SR) mdconfig -d -u $$md";			\
	 	echo "$$cmd"; eval "$$cmd" || exit $$?;			\
	 done;								\
	 cmd="gzip \"$$mfsroot\""; echo "$$cmd"; eval "$$cmd"

update_static: stage0

from_dep: stage1 stage2 stage3 stage4

remake: stage2 stage3 stage4

open: stage2

copy: stage3

close: stage4

dep/mfsroot.gz:
	mkdir -p dep
	@. "$(STATIC_CONF)" || exit $$?;			\
	 if [ ! "$$STATIC_BASE" ]; then				\
	 	echo "!!! STATIC_BASE not defined"		\
	 	     "in $(STATIC_CONF)" >&2;			\
	 	exit 1;						\
	 fi;							\
	 if [ -f "$$STATIC_BASE/boot/boot" ]; then		\
	 	BOOT="-B -b $$STATIC_BASE/boot/boot";		\
	 else							\
	 	BOOT="-r";					\
	 fi;							\
	 cleanup=;						\
	 cmd="dd if=/dev/zero of=dep/mfsroot";			\
	 cmd="$$cmd count=$(MFSSIZE) bs=1k";			\
	 echo "$$cmd"; eval "$$cmd" || exit $$?;		\
	 cleanup="rm -f dep/mfsroot; $$cleanup";		\
	 trap "$$cleanup" EXIT;					\
	 cmd="$(SR) mdconfig -at vnode -f dep/mfsroot";		\
	 echo "$$cmd"; md=$$( eval "$$cmd" ) || exit $$?;	\
	 cleanup="$(SR) mdconfig -d -u $${md#md}; $$cleanup";	\
	 trap "$$cleanup" EXIT;					\
	 if type bsdlabel > /dev/null 2>&1; then		\
	 	DISKLABEL="bsdlabel";				\
	 else							\
	 	DISKLABEL="disklabel";				\
	 fi;							\
	 cmd="$(SR) $$DISKLABEL -w $$BOOT $$md auto";		\
	 echo "$$cmd"; eval "$$cmd" || exit $$?;		\
	 cmd="$(SR) newfs -n -O1 -b 4096 -f 512";		\
	 cmd="$$cmd -i $(MFSINODE) -o space -m 0 /dev/$$md";	\
	 echo "$$cmd"; eval "$$cmd" || exit $$?;		\
	 trap - EXIT;						\
	 cmd="$(SR) mdconfig -d -u $${md#md}";			\
	 echo "$$cmd"; eval "$$cmd" || exit $$?;		\
	 cmd="gzip -9 --no-name -fv dep/mfsroot";		\
	 echo "$$cmd"; eval "$$cmd"
	 

almostclean:
	$(SR) find static -type f -delete

clean:
	rm -f dep/mfsroot.gz || true
	[ ! -d dep ] || rmdir dep || true
	[ ! -d src/netroot ] || rmdir src/netroot || true
	@if [ -f "$(STATIC_CONF)" ]; then	\
	 	. "$(STATIC_CONF)" || exit $$?;	\
	 fi;					\
	 if [ "$$OUTPUT" ]; then		\
	 	cmd="rm -f \"$$OUTPUT\"";	\
	 	echo "$$cmd"; eval "$$cmd";	\
	 fi;					\
	 if [ -d static ]; then			\
	 	cmd="$(SR) rm -Rf static";	\
	 	echo "$$cmd"; eval "$$cmd";	\
	 fi

distclean: clean
	rm -f "$(STATIC_CONF)"

install:
	@. "$(STATIC_CONF)" || exit $$?;				\
	 if [ ! "$$DESTDIR" ]; then					\
	 	echo "!!! DESTDIR not defined in" "$(STATIC_CONF)" >&2;	\
	 	exit 1;							\
	 fi;								\
	 if [ ! "$$OUTPUT" ]; then					\
	 	echo "!!! OUTPUT not defined in $(STATIC_CONF)" >&2;	\
	 	exit 1;							\
	 fi;								\
	 if [ ! -f "$$OUTPUT" ]; then					\
	 	cmd="$(MAKE) all";					\
	 	echo "$$cmd"; eval "$$cmd" || exit $$?;			\
	 fi;								\
	 cmd="$(SR) cp -f \"$$OUTPUT\" \"$${DESTDIR%/}/\"";		\
	 echo "$$cmd"; eval "$$cmd"

archive: distclean
	@if ! version=$$( awk '						\
	   $$1 == "VERSION" && $$2 == "=" { print $$3; exit }		\
	   $$1 == "VERSION=" { print $$2; exit }			\
	   $$1 ~ /VERSION=.+/ { sub(/[^=]*=/, ""); print $$1; exit }	\
	 ' version.inf ); then						\
	 	echo "!!! Unable to get VERSION from version.inf" >&2;	\
	 	exit 1;							\
	 fi;								\
	 cmd="tar -c --exclude '*/CVS/*' --exclude 'CVS/*' -f - .";	\
	 cmd="$$cmd | xz -9 - > ../$(ARCHIVE)-$$version.txz";		\
	 echo "$$cmd"; eval "$$cmd"

################################################################################
#
# $Header: /cvsroot/druidbsd/pxe-config/netboot/Makefile,v 1.6 2014/03/02 01:59:59 devinteske Exp $
#
# $Copyright: 2006-2014 Devin Teske. All rights reserved. $
#
# $Log: Makefile,v $
# Revision 1.6  2014/03/02 01:59:59  devinteske
# Allow clean target to succeed even if we do something, like, mark the
# mfsroot.gz dep as system-immutable (schg)
#
# Revision 1.5  2014/03/01 22:16:50  devinteske
# Add `CVS' directories to tar(1) exclude to prevent archival during the
# `make archive' target.
#
# Revision 1.4  2014/03/01 22:15:53  devinteske
# Add `-n' to newfs(8) call to prevent creation of `.snap' directory (which
# is already generated via mtree(8) part of process).
#
# Revision 1.3  2014/03/01 10:19:47  devinteske
# Obfuscate CVS keyword to prevent expansion in this one singular occurrance
# and also make a change to copy `version.inf' into the compiled output for
# additional change tracking.
#
# Revision 1.2  2014/03/01 04:24:18  devinteske
# Fix incorrect inode count which makes FreeBSD-11 very cranky (panics)
#
# Revision 1.1  2014/03/01 02:14:35  devinteske
# Import initial revision 1.0 of pxe-config and netboot framework (champagne
# worthy celebration).
#
#
################################################################################
