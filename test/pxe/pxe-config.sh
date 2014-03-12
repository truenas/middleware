#!/bin/sh
#-
############################################################ IDENT(1)
#
# $Title: Script for preparing one or more ISO images for PXE boot $
#
############################################################ COPYRIGHT
#
# (c)2014. Devin Teske. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#
# $Header: /cvsroot/druidbsd/pxe-config/pxe-config.sh,v 1.29 2014/03/02 05:29:13 devinteske Exp $
#
############################################################ INCLUDES

#
# We're 50% console utility and 50% dialog(1)/Xdialog(1) utility
# ... so tell the dialog library to not initialize itslef on-load.
#
DIALOG_SELF_INITIALIZE=

BSDCFG_SHARE="/usr/share/bsdconfig"
. $BSDCFG_SHARE/common.subr || exit 1
f_dprintf "%s: loading includes..." "$0"
f_include $BSDCFG_SHARE/dialog.subr
f_include $BSDCFG_SHARE/strings.subr
f_include $BSDCFG_SHARE/struct.subr

############################################################ CONFIGURATION

#
# Where to find ISO files when configuring the PXE menu
#
ISOIMPORT_DIR="/images"

#
# Filter against ISO files to find in the import directory
# NB: Only items matching this pattern are acted-on when using `-A' or `-a'
# NB: This is an awk(1) regular expression
#
ISOFILTER="^(Free|True).+"

#
# Base path to NFS/SMB exported directory to unpack ISO to
#
# NB: Feel free to set this to $ISOIMPORT_DIR but beware that the files are
#     unpacked as `root' so will may be immutable to the user that uploaded
#     the original ISO into the same directory. However, you can always use
#     the `-R' flag to prune entries.
#
ROOTEXPORT_DIR="/pxe"

#
# Path to our boot image build-framework
#
NETBOOT_SRC="$0"
NETBOOT_SRC="${NETBOOT_SRC%/*}/netboot"

#
# What is the IP address of the HTTP server (usually this machine) that serves
# the netboot ISO images?
#
# NB: If not this machine, make sure the $HTTP_DATA files get pushed there
#
HTTP_SERVER="192.168.1.1"

#
# URI to the HTTP exported directory serving pxe-config ISOs
# NB: Served from $HTTP_DATA as configured in `httpd.conf'
# NB: This can be a directory or symlink (e.g., to $ROOTEXPORT_DIR)
#
ISOEXPORT_URI="/pxe"

############################################################ MORE CONFIGURATION

#
# Samba configuration file and template
#
SMB_CONF_TEMPLATE="/usr/local/etc/smb.conf.template"
SMB_CONF="${SMB_CONF_TEMPLATE%.*}"

#
# syslinux menu configuration file and template
#
MENU_CONF_TEMPLATE="/tftpboot/boot/pxe-config/isolinux.cfg.template"
MENU_CONF="${MENU_CONF_TEMPLATE%.*}"

#
# Text to replace `@TITLE@` in $MENU_CONF_TEMPLATE with
#
MENU_TITLE="ISO Options:"

#
# apache httpd DocumentRoot (configured in `httpd.conf')
#
HTTP_DATA="/usr/local/www/apache22/data"

#
# Where to temporarily mount the ISO
#
ISO_MNT="/tmp/pxe-config.iso.$$"

#
# Where to temporarily mount FreeNAS md(4) volume (e.g., base.ufs.uzip)
#
MD_MNT="/tmp/pxe-config.md.$$"

############################################################ GLOBALS

# Exit status variables
SUCCESS=0
FAILURE=1

#
# Command-line options
#
ACT_ON_ALL=
ACT_ON_INACTIVE=
ALWAYS_STAGE=
CHECK_ONLY=
NO_HTTP_ISO=
NO_IMAGE=
NO_SAVE=
NO_SYNC=
QUIET=
REMOVE=
UPDATE_PXE=
USE_SMB=1
USE_XDIALOG=
VERBOSE=

#
# mkisofs(8) options
#
MKISOFS_OPTS="-U -J -r"

#
# Structure for tracking `ISO_ENTRIES'
#
f_struct_define ISO_ENTRY \
	active	\
	file	\
	label	\
	rootdir	\
	uri

#
# A Literal newline (for use with f_replace_all(), or IFS, or whatever)
#
NL="
" # END-QUOTE

#
# Tag prefixes for PXE menu (limits the number of ISOs)
#
MENU_TAGS="123456789abcdefghijklmnopqrstuvwyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

#
# These weren't defined by bsdconfig(8)'s `dialog.subr' until releng/10.0
#
DIALOG_OK=${SUCCESS:-0}
DIALOG_CANCEL=${FAILURE:-1}
export DIALOG_ERROR=254 # sh(1) can't handle the default of `-1'
DIALOG_ESC=255

############################################################ I18N

#
# Strings that should be moved to an i18n file and loaded with f_include_lang()
#
msg_abort_remaining="Abort remaining steps?"
msg_active="active"
msg_all_active="All active!"
msg_creating="Creating"
msg_enabling_x11_mode="Enabling X11 mode (unset \$DISPLAY to prevent)"
msg_ignoring_error_status_from="Ignoring error status from %s"
msg_inactive="inactive"
msg_no_iso_files_found_in_dir="No ISO files found in %s"
msg_one_or_more_inactive="One or more inactive (use \`-v' for details)!"
msg_pxe_boot_configuration_menu="PXE boot configuration menu. Press ESC or Ctrl-C to abort changes."
msg_removing="Removing"
msg_save_exit="Save/Exit"
msg_saving_pxe_configuration="Saving PXE configuration..."
msg_some_items_failed="Some items failed!"
msg_successfully_updated_pxe_boot_configuration_file="Successfully updated PXE boot configuration file!"
msg_successfully_updated_smb_configuration_file="Successfully updated SMB configuration file!"
msg_truncating="Truncating %s"
msg_unknown_error_occurred_unable_to_save="Unknown error occurred. Unable to save!"
msg_unpacking="Unpacking"
xmsg_pxe_boot_configuration_menu="PXE boot configuration menu. Close window to prevent changes."

############################################################ FUNCTIONS

# usage
#
# Print a short usage statment and exit with error status.
#
usage()
{
	local argfmt="\t%-11s %s\n" optfmt="\t%-9s %s\n"
	f_err "Usage: %s\n" "$0"
	f_err "       %s -h\n" "$0"
	f_err "       %s -l\n" "$0"
	f_err "       %s [OPTIONS] [isofile | -a | -A | -U]\n" "$0"
	f_err "\nARGUMENTS:\n"
	f_err "$argfmt" -A      "Operate on all images in the import directory"
	f_err "$argfmt" -a      \
	      "Operate on all inactive images in the import directory"
	f_err "$argfmt" -h      "Print this message and exit"
	f_err "$argfmt" isofile "Path to ISO file to unpack"
	f_err "$argfmt" -l      "List files and status (synonym for \`-cAv')"
	f_err "$argfmt" -U      "Update PXE files and exit"
	f_err "\nOPTIONS:\n"
	f_err "$optfmt" -1 "Perform first staging step (synonym for \`-iIu')"
	f_err "$optfmt" "" "This stage consists of unpacking isofile to disk"
	f_err "$optfmt" -2 "Perform second staging step (synonym for \`-nIu')"
	f_err "$optfmt" "" "This stage consists of generating boot image"
	f_err "$optfmt" -3 "Perform third staging step (synonym for \`-niu')"
	f_err "$optfmt" "" "This stage consists of creating the netboot ISO"
	f_err "$optfmt" -d "Enable debugging output to terminal standard out"
	f_err "$optfmt" -c "Only check to see if isofile is currently active"
	f_err "$optfmt" -I "Don't [re-]create HTTP netboot ISO image"
	f_err "$optfmt" -i "Don't [re-]create interim netboot image"
	f_err "$optfmt" -N "Tell netboot image to use NFS instead of SMB"
	f_err "$optfmt" -n "Don't update ISO directory with ISO contents"
	f_err "$optfmt" -p "In the menu, always stage activated ISOs"
	f_err "$optfmt" -q "Quiet. Quell normal messages to stdout"
	f_err "$optfmt" -R "Remove prepared files associated with isofile"
	f_err "$optfmt" -s "Tell netboot image to use SMB instead of NFS"
	f_err "$optfmt" -u "Don't modify PXE or SMB configuration files"
	f_err "$optfmt" -v "Verbose. Provide voluminous output"
	f_err "$optfmt" -X "X11 mode. Use Xdialog(1) instead of dialog(1)"
	die
}

# die [$format [$arguments ...]]
#
# Exit with failure, optionally printing a message to standard error using
# printf(1) syntax.
#
die()
{
	local format="$1"
	[ $# -gt 0 ] && shift 1 && f_err "$format\n" "$@"
	exit $FAILURE
}

# eval2 $command [$arguments ...]
#
# Execute a command after first printing it to standard out.
#
eval2()
{
	echo "$@"
	eval "$@"
}

# unpack_iso $isofile
#
# Unpack an ISO9660 file (*.iso) to `$ROOTEXPORT_DIR/<name>' where `<name>' is
# the filename of $isofile (leading path element(s) stripped).
#
# NB: Uses mdconfig(8) rather than tar(1) because bsdtar(1) has some bugs in
# handling ISO files in 9.2-RELEASE and [more importantly] so we can utilize
# rsync(1) to synchronize the data for speeding things up.
#
# Global variables required:
#
# 	ROOTEXPORT_DIR	Base path to NFS/SMB exported directory to unpack to
# 	ISO_MNT		Where to temporarily mount the ISO
# 	MD_MNT		Where to temporarily mount FreeNAS md(4) volume
#
# Global variables set:
#
# 	ISO_CLEAN	If non-NULL, command to `eval' to clean-up after ISO
# 	MD_CLEAN	If non-NULL, command to `eval' to clean-up after md(4)
#
unpack_iso()
{
	local iso_file="$1"
	local iso_filename="${iso_file##*/}"
	local output_dir="$ROOTEXPORT_DIR/${iso_filename%.iso}"
	local keep_loader_conf=

	if [ ! -f "$iso_file" ]; then
		printf "$msg_no_such_file_or_directory\n" \
		       "$pgm" "$iso_file" >&2
		return $FAILURE
	fi

	#
	# Attempt to attach to ISO file and mount it
	#
	local md
	ISO_CLEAN=
	eval2 md=\$\( mdconfig -f "'$iso_file'" \) || return $?
	    ISO_CLEAN="eval2 mdconfig -d -u ${md#md}; $ISO_CLEAN"
	    trap "$ISO_CLEAN" EXIT
	eval2 mkdir -p "'$ISO_MNT'" || return $?
	    ISO_CLEAN="eval2 rmdir '$ISO_MNT'; $ISO_CLEAN"
	    trap "$ISO_CLEAN" EXIT
	eval2 mount_cd9660 /dev/$md "'$ISO_MNT'" || return $?
	    ISO_CLEAN="eval2 umount '$ISO_MNT'; $ISO_CLEAN"
	    trap "$ISO_CLEAN" EXIT

	#
	# If the ISO has a `.mount.conf' file (see mount.conf(8)), process it
	# to find the [actual] root data that we should extract.
	#
	local md_filename md_type md_dev md_options
	if [ -f "$ISO_MNT/.mount.conf" ]; then
		f_dprintf "Processing %s" "$ISO_MNT/.mount.conf"
		eval "$( awk '
		function set_var(var, value)
		{
			print var "=\"" value "\""
		}
		$1 == ".md" { set_var("md_filename", $2) }
		$1 ~ /^[[:alpha:]]+:/ {
			type = dev = $1
			sub(/:.*/, "", type)
			sub(/[^:]*:/, "", dev)
			sub(/^[[:space:]]*[^[:space:]]+[[:space:]]*/, "", $0)
			set_var("md_type", type)
			set_var("md_dev", dev)
			set_var("md_options", $0)
			exit # Only process the first entry
		}
		' "$ISO_MNT/.mount.conf" || echo false )" || return $FAILURE
		f_dprintf "md_filename=[$md_filename]"
		f_dprintf "md_type=[$md_type]"
		f_dprintf "md_dev=[$md_dev]"
		f_dprintf "md_options=[$md_options]"
	fi

	#
	# If we processed `.mount.conf' from the ISO media, attempt to prepare
	# another md(4) device to get the data from. Otherwise, just copy the
	# data from the mounted ISO filesystem.
	#
	if [ "$md_filename" -a "$md_type" -a "$md_dev" ]; then
		#
		# Make sure we have the geom_uzip module loaded if-needed
		#
		case "$md_dev" in *.uzip)
			eval2 f_quietly kldstat -n geom_uzip ||
				eval2 kldload geom_uzip || return $?
		esac

		#
		# Attempt to configure and mount the md(4) device
		#
		MD_CLEAN=
		eval2 data_md=\$\( mdconfig -a -o readonly \
			-f "'$ISO_MNT/${md_filename#/}'" \) || return $?
		    MD_CLEAN="eval2 mdconfig -d -u ${data_md#md}; $MD_CLEAN"
		    trap "$MD_CLEAN; $ISO_CLEAN" EXIT
		while case "$md_dev" in *"#"*) true ;; *) false ; esac; do
			md_dev="${md_dev%%#*}${data_md#md}${md_dev#*#}"
		done
		eval2 mkdir -p "'$MD_MNT'" || return $?
		    MD_CLEAN="eval2 rmdir '$MD_MNT'; $MD_CLEAN"
		    trap "$MD_CLEAN; $ISO_CLEAN" EXIT
		eval2 mount ${md_options:+-o '$md_options'} \
			-t $md_type "'$md_dev'" "'$MD_MNT'" || return $?
		    MD_CLEAN="eval2 umount '$MD_MNT'; $MD_CLEAN"
		    trap "$MD_CLEAN; $ISO_CLEAN" EXIT

		# Synchronize the MD directory with NFS/SMB exported directory
		eval2 rsync -avH "'$MD_MNT/'" "'$output_dir/'" || return $?
		[ -e "$MD_MNT/boot/loader.conf" ] && keep_loader_conf=1

		#
		# All done with this md(4) device; cleanup
		#
		trap "$ISO_CLEAN" EXIT
		eval "$MD_CLEAN" || MD_CLEAN= return $?

		#
		# If there is a `.mount' directory in the data we just unpacked
		# then re-unpack the ISO directory to `.mount' -- this matches
		# the vfs_mountroot() functionality documented in mount.conf(8)
		#
		if [ -d "$output_dir/.mount" ]; then
			eval2 rsync -avH \
				"'$ISO_MNT/'" "'$output_dir/.mount'" ||
				return $?
			[ -e "$ISO_MNT/boot/loader.conf" ] &&
				keep_loader_conf=1
		fi

		#
		# Touch up the `/boot' directory if it is a symlink
		#
		# NB: Since `/boot' is a symlink in the base of the root-fs,
		# simply removing the leading-`/' from it will do nicely.
		#
		if [ -L "$output_dir/boot" ]; then
			local path
			path=$( readlink "$output_dir/boot" )
			case "$path" in
			/*) eval2 ln -sf "'${path#/}'" "'$output_dir/boot'" ||
				return $? ;;
			esac
		fi
	else
		# Synchronize the ISO directory with NFS/SMB exported directory
		eval2 rsync -avH "'$ISO_MNT/'" "'$output_dir/'" || return $?
		[ -e "$ISO_MNT/boot/loader.conf" ] && keep_loader_conf=1
	fi

	#
	# Cleanup
	#
	trap - EXIT
	eval "$ISO_CLEAN" || ISO_CLEAN= return $?
	ISO_CLEAN= 

	#
	# Touch up `/bin/sh' in the ISO directory if it is a symlink
	#
	local bin_sh="$output_dir/bin/sh" path
	if [ -L "$bin_sh" ]; then
		path=$( readlink "$bin_sh" )
		case "$path" in /*)
			eval2 ln -sf "'..$path'" "'$bin_sh'" || return $?
		esac
	fi

	#
	# [Re-]Touch up `/etc/fstab' in the ISO directory
	# NB: rsync(1) would have reverted fstab changed
	#
	if [ -e "$output_dir/etc/fstab" ]; then
		eval2 mv -fv "'$output_dir/etc/fstab'" \
		             "'$output_dir/etc/fstab.orig'"
		[ $? -eq $SUCCESS ] ||
			printf "# $msg_ignoring_error_status_from\n" \
			       "mv(1)" >&2
	fi
	printf "$msg_truncating\n" "$output_dir/etc/fstab"
	( :> "$output_dir/etc/fstab" ) || return $?

	#
	# Kill loader.conf(5) in the ISO directory if there wasn't one in the
	# original ISO itself (preventing multiply-appending later in stage-2).
	#
	# NB: If there *was* a loader.conf(5) in the original ISO, the above
	# rsync(1) would have reverted it to the contents on the original ISO
	# (making later stage-2 appending still-copacetic).
	#
	if [ -f "$output_dir/boot/loader.conf" -a ! "$keep_loader_conf" ]; then
		eval2 rm -f "'$output_dir/boot/loader.conf'" || return $?
	fi

	return $SUCCESS
}

# create_netboot_image $isofile
#
# Create the `netboot.gz' boot image to be used as an `mfs_root' module with
# the installer's kernel and loader files. This boot image merely uses `kenv'
# to fetch either the `boot.nfsroot.path' or `boot.smbroot.share' variable set
# in the kernel's loader.conf(5) file -- subsequently mounting the desired
# path (NFS) or share (SMB) from the DHCP server that it booted from.
#
# Global variables required:
#
# 	ROOTEXPORT_DIR	Base path to NFS/SMB exported directory to unpack to
# 	NETBOOT_SRC	Path to boot image build-framework
# 	MD_MNT		Where to temporarily mount FreeNAS md(4) volume
#
# Global variables set:
#
# 	MD_CLEAN	If non-NULL, command to `eval' to clean-up after md(4)
#
create_netboot_image()
{
	local iso_file="$1"
	local iso_filename="${iso_file##*/}"
	local iso_dir="$ROOTEXPORT_DIR/${iso_filename%.iso}"
	local static_base="$iso_dir" # May change below if using AVATAR media
	local output_dir="$ROOTEXPORT_DIR/${iso_filename%.iso}"
	local output="$output_dir/boot/${NETBOOT_SRC##*/}.gz"

	if [ ! -d "$NETBOOT_SRC" ]; then
		printf "$msg_no_such_file_or_directory\n" "$pgm" \
		       "$NETBOOT_SRC" >&2
		return $FAILURE
	fi
	if [ ! -d "$iso_dir" ]; then
		printf "$msg_no_such_file_or_directory\n" "$pgm" "$iso_dir" >&2
		return $FAILURE
	fi
	if [ ! -d "${output%/*}" ]; then
		printf "$msg_no_such_file_or_directory\n" \
		       "$pgm" "${output%/*}" >&2
		return $FAILURE
	fi

	#
	# Attempt to read AVATAR based installer configuration
	#
	local avatar_project avatar_arch avatar_conf="$iso_dir/etc/avatar.conf"
	if [ -f "$avatar_conf" ]; then
		eval2 avatar_project=\$\( sysrc -nf "'$avatar_conf'" \
			AVATAR_PROJECT \) || return $?
		eval2 avatar_arch=\$\( sysrc -nf "'$avatar_conf'" \
			AVATAR_ARCH \) || return $?
	fi

	#
	# If this is an AVATAR based installer, use the OS data itself
	#
	local avatar_image="$iso_dir/.mount/$avatar_project-$avatar_arch.img"
	if [ "$avatar_project" -a "$avatar_arch" -a -f "$avatar_image.xz" ]
	then
		local md
		[ -f "$avatar_image" ] || eval2 \
			xzcat "'$avatar_image.xz'" \> "'$avatar_image'" ||
			return $?
		MD_CLEAN=
		eval2 md=\$\( mdconfig -f "'$avatar_image'" \) || return $?
		    MD_CLEAN="eval2 mdconfig -d -u ${md#md}; $MD_CLEAN"
		    trap "$MD_CLEAN" EXIT
		eval2 mkdir -p "'$MD_MNT'" || return $?
		    MD_CLEAN="eval2 rmdir '$MD_MNT'; $MD_CLEAN"
		    trap "$MD_CLEAN" EXIT
		eval2 mount /dev/${md}s1a "'$MD_MNT'" || return $?
		    MD_CLEAN="eval2 umount '$MD_MNT'; $MD_CLEAN"
		    trap "$MD_CLEAN" EXIT
		static_base="$MD_MNT"
	fi

	#
	# Attempt to configure and install boot-image
	#
	eval2 sysrc -f "'$NETBOOT_SRC/etc/static.conf'" \
		STATIC_BASE="'$static_base'" OUTPUT="'${output##*/}'" \
		DESTDIR="'$iso_dir/boot'" || return $?
	eval2 cd "$NETBOOT_SRC" || return $?
	if [ "$VERBOSE" ]; then
		eval2 make clean install
	else
		( make clean install ) > /dev/null 2>&1
	fi
	if [ $? -ne $SUCCESS ]; then
		eval2 cd -
		return $FAILURE
	fi
	eval2 cd - || return $?

	#
	# Cleanup
	#
	trap - EXIT
	eval "$MD_CLEAN" || MD_CLEAN= return $?
	MD_CLEAN= 

	return $SUCCESS
}

# create_netboot_iso $isofile
#
# Create the `*.netboot.iso' ISO9660 file to be stored in the HTTP exported
# directory. This boot ISO merely boots, invokes loader, loads loader.conf,
# boots a kernel (extracted from unpacked original-ISO), invokes `netboot.gz'
# boot-image which then mounts (either via NFS or SMB) the original ISO from
# the DHCP server. This routine automates the generation of both loader.conf
# and the `netboot.iso' file that is initially booted via lpxelinux.0's memdisk
# module.
#
# Global variables required:
#
# 	ROOTEXPORT_DIR	Base path to NFS/SMB exported directory to unpack to
# 	NETBOOT_SRC	Path to boot image build-framework
# 	USE_SMB		Set to non-NULL to use SMB instead of NFS
# 	HTTP_DATA	Path to HTTP exported directory
# 	ISOEXPORT_URI	URI of exported directory to store `netboot.iso'
# 	MKISOFS_OPTS	Base mkisofs(8) options (usually `-U -J -r')
#
create_netboot_iso()
{
	local iso_file="$1"
	local iso_filename="${iso_file##*/}"
	local iso_name="${iso_filename%.iso}"
	local iso_dir="$ROOTEXPORT_DIR/${iso_filename%.iso}"
	local output_dir="$HTTP_DATA/${ISOEXPORT_URI#/}"
	local output="$output_dir/$iso_name.${NETBOOT_SRC##*/}.iso"

	if [ ! -d "$iso_dir/boot" ]; then
		printf "$msg_no_such_file_or_directory\n" \
		       "$pgm" "$iso_dir/boot" >&2
		return $FAILURE
	fi
	if [ ! -d "${output%/*}" ]; then
		printf "$msg_no_such_file_or_directory\n" \
		       "$pgm" "${output%/*}" >&2
		return $FAILURE
	fi

	#
	# Touch up loader.conf(5) contents before generating `netboot.iso'
	# NB: Only if it appears that we have not already done-so
	#
	local loader_entry loader_conf="$iso_dir/boot/loader.conf"
	if [ "$USE_SMB" ]; then
		loader_entry="boot.smbroot.share=\"${iso_dir##*/}\""
	else
		loader_entry="boot.nfsroot.path=\"$iso_dir\""
	fi
	if ! awk -v entry="$loader_entry" \
		'$0 == entry { found++; exit } END { exit ! found }' \
		"$loader_conf" 2> /dev/null
	then
		echo "# $msg_creating $loader_conf"

		#
		# Load a facsimile of the current loader.conf(5) -- minus
		# certain elements that we want to lay down ourselves.
		#
		local current_contents=
		[ -f "$loader_conf" ] && current_contents=$( awk \
			'!/^[[:space:]]*vfs\.root\./{print}' \
			"$loader_conf" )

		#
		# Entries required to boot [previously generated] `netboot.gz'
		#
		local loader_entry
		( cat <<-EOF > "$loader_conf" ) || return $?
		${current_contents:+$current_contents
		
		}# ${NETBOOT_SRC##*/} loader.4th(8) configuration
		mfsroot_load="YES"
		mfsroot_type="mfs_root"
		mfsroot_name="boot/${NETBOOT_SRC##*/}"
		vfs.root.mountfrom="ufs:/dev/md0"
		vfs.root.mountfrom.options="rw"${USE_SMB:+
		smbfs_load="YES"}

		# ${NETBOOT_SRC##*/} options
		$loader_entry
		EOF
	fi

	#
	# Pre-adjust for AVATAR based media
	#
	[ -d "$iso_dir/.mount/boot" ] && iso_dir="$iso_dir/.mount"

	#
	# Attempt to create the netboot ISO
	#
	eval2 cd "'$iso_dir'" || return $?
	if [ "$VERBOSE" ]; then
		eval2 mkisofs $MKISOFS_OPTS -V "'${NETBOOT_SRC##*/}'" \
			-b boot/cdboot -no-emul-boot -c boot.catalog \
			-boot-load-size 4 -o "'$output'" \
			-graft-points /boot=boot || return $?
	else
		eval2 mkisofs $MKISOFS_OPTS -V "'${NETBOOT_SRC##*/}'" \
			-b boot/cdboot -no-emul-boot -c boot.catalog \
			-boot-load-size 4 -o "'$output'" \
			-graft-points /boot=boot > /dev/null 2>&1 || return $?
	fi
	eval2 cd - || return $?

	#
	# Post-adjust for AVATAR based media
	#
	[ "${iso_dir##*/}" = ".mount" ] && iso_dir="${iso_dir%/*}"

	#
	# Special considerations
	#
	if [ "$USE_SMB" ]; then
		eval2 sysrc -f "'$iso_dir/etc/rc.conf'" root_rw_mount=NO ||
			return $?
	fi

	return $SUCCESS
}

# process_one $isofile
#
# Process a single $isofile, wholly and completely.
#
# Global variables required:
#
# 	ROOTEXPORT_DIR	Base path to NFS/SMB exported directory to unpack to
# 	NETBOOT_SRC	Path to boot image build-framework
# 	ISOEXPORT_URI	URI of exported directory to store `netboot.iso'
#
process_one()
{
	local isofile="$1"
	local iso_filename="${isofile##*/}"
	local iso_name="${iso_filename%.iso}"

	[ -f "$isofile" ] || return $FAILURE

	#
	# Update the unpacked ISO directory with ISO contents
	#
	if [ ! "$NO_SYNC" ]; then
		[ "$QUIET" ] ||
			printf ">>> $msg_unpacking %s\n" "${isofile##*/}"
		if [ "$VERBOSE" ]; then
			unpack_iso "$isofile"
		else
			eval unpack_iso \"\$isofile\" \
				\> /dev/null ${QUIET:+2>&1}
		fi || return $?
	fi

	#
	# Create the `netboot.gz' image
	#
	if [ ! "$NO_IMAGE" ]; then
		[ "$QUIET" ] || printf ">>> $msg_creating %s\n" \
			"$ROOTEXPORT_DIR/$iso_name/boot/${NETBOOT_SRC##*/}.gz"
		if [ "$VERBOSE" ]; then
			create_netboot_image "$isofile"
		else
			eval create_netboot_image \"\$isofile\" \
				\> /dev/null ${QUIET:+2>&1}
		fi || return $?
	fi

	#
	# Create the `netboot.iso' image
	#
	if [ ! "$NO_HTTP_ISO" ]; then
		[ "$QUIET" ] || printf ">>> $msg_creating %s\n" \
			"$ISOEXPORT_URI/$iso_name.${NETBOOT_SRC##*/}.iso"
		if [ "$VERBOSE" ]; then
			create_netboot_iso "$isofile"
		else
			eval create_netboot_iso \"\$isofile\" \
				\> /dev/null ${QUIET:+2>&1}
		fi || return $?
	fi

	return $SUCCESS
}

# remove_one $isofile
#
# Remove generated files associated with a single $isofile.
#
# Global variables required:
#
# 	ROOTEXPORT_DIR	Base path to NFS/SMB exported directory to unpack to
# 	NETBOOT_SRC	Path to boot image build-framework
# 	ISOEXPORT_URI	URI of exported directory to store `netboot.iso'
#
remove_one()
{
	local isofile="$1"
	local iso_filename="${isofile##*/}"
	local iso_name="${iso_filename%.iso}"
	local iso_dir="$ROOTEXPORT_DIR/$iso_name"
	local boot_iso="$ISOEXPORT_URI/$iso_name.${NETBOOT_SRC##*/}.iso"

	[ -f "$isofile" ] || return $FAILURE

	#
	# Remove the unpacked ISO directory
	#
	[ "$QUIET" ] || printf ">>> $msg_removing %s\n" "$iso_dir"
	if [ "$VERBOSE" ]; then
		eval2 rm -Rfv "'$iso_dir'"
	else
		eval rm -Rf \"\$iso_dir\" \> /dev/null ${QUIET:+2>&1}
	fi

	#
	# Remove the `netboot.iso' image
	#
	[ "$QUIET" ] || printf ">>> $msg_removing %s\n" "$boot_iso"
	if [ "$VERBOSE" ]; then
		eval2 rm -fv "'$HTTP_DATA$boot_iso'"
	else
		eval rm -f \"\$HTTP_DATA\$boot_iso\" \
			\> /dev/null ${QUIET:+2>&1}
	fi

	#
	# Remove the `.ignore' file if it exists
	#
	if [ -e "$HTTP_DATA$boot_iso.ignore" ]; then
		[ "$QUIET" ] ||
			printf ">>> $msg_removing %s\n" "$boot_iso.ignore"
		if [ "$VERBOSE" ]; then
			eval2 rm -fv "'$HTTP_DATA$boot_iso.ignore'"
		else
			eval rm -f \"\$HTTP_DATA\$boot_iso.ignore\" \
				\> /dev/null ${QUIET:+2>&1}
		fi
	fi

	return $SUCCESS
}

# scan_iso_entries
#
# Populate $ISO_ENTRIES with a list of struct names (minus `isoentry_' prefix)
# representing both active and inactive ISO entries. See struct definition for
# ISO_ENTRY structure in GLOBALS section at top.
#
# Global variables required:
#
# 	ROOTEXPORT_DIR	Base path to NFS/SMB exported directory to unpack to
# 	NETBOOT_SRC	Path to boot image build-framework
# 	HTTP_DATA	Path to HTTP exported directory
# 	ISOEXPORT_URI	URI of exported directory to store `netboot.iso'
# 	ISOIMPORT_DIR	Where to find original ISO files for import
#
scan_iso_entries()
{
	ISO_ENTRIES=

	#
	# Build internal list of potentially-active and inactive configurations
	#
	local path iso_filename label name
	for path in "$HTTP_DATA/${ISOEXPORT_URI#/}"/*.${NETBOOT_SRC##*/}.iso
	do
		[ -e "$path" ] || continue # Case of no match expansion
		iso_filename="${path##*/}"
		# Check the name of the ISO file against filter
		echo "$iso_filename" | awk -v filter="$ISOFILTER" \
			'$0~filter{found++; exit}END{exit ! found}' ||
			continue # Skip if ISO doesn't match filter
		label="${iso_filename%.iso}"
		f_str2varname "$label" name
		f_struct_new ISO_ENTRY isoentry_$name || return $FAILURE
		isoentry_$name set active  ""
		isoentry_$name set file    \
			"$ISOIMPORT_DIR/${label%.${NETBOOT_SRC##*/}*}.iso"
		isoentry_$name set label   "$label"
		isoentry_$name set uri     "$ISOEXPORT_URI/$iso_filename"
		isoentry_$name set rootdir \
			"$ROOTEXPORT_DIR/${label%.${NETBOOT_SRC##*/}*}"
		ISO_ENTRIES="$ISO_ENTRIES $name"
	done
	local path iso_filename label name
	for path in "$ISOIMPORT_DIR"/*.iso; do
		[ -e "$path" ] || continue # Case of no match expansion
		iso_filename="${path##*/}"
		# Check the name of the ISO file against filter
		echo "$iso_filename" | awk -v filter="$ISOFILTER" \
			'$0~filter{found++; exit}END{exit ! found}' ||
			continue # Skip if ISO doesn't match filter
		label="${iso_filename%.iso}.${NETBOOT_SRC##*/}"
		f_str2varname "$label" name
		case "$ISO_ENTRIES" in
		"$name"|"$name"[$IFS]*|*[$IFS]"$name"[$IFS]*|*[$IFS]"$name")
			continue ;;
		esac
		f_struct_new ISO_ENTRY isoentry_$name || return $FAILURE
		isoentry_$name set active  ""
		isoentry_$name set file    "$path"
		isoentry_$name set label   "$label"
		isoentry_$name set uri     "$ISOEXPORT_URI/$label.iso"
		isoentry_$name set rootdir \
			"$ROOTEXPORT_DIR/${iso_filename%.iso}"
		ISO_ENTRIES="$ISO_ENTRIES $name"
	done

	#
	# Mark active entries as such
	#
	local i rootdir uri
	for i in $ISO_ENTRIES; do
		f_struct isoentry_$i || continue # Pedantic
		isoentry_$i get rootdir rootdir
		isoentry_$i get uri     uri
		[ -d "$rootdir" -a ! -e "$HTTP_DATA$uri.ignore" ] &&
			isoentry_$i set active 1
	done

	return $SUCCESS
}

# check_one $isofile [$var_to_set]
#
# For the ``check-only'' option (which reports the active/inactive status of
# an $isofile with respect to visibility in the PXE menu, this function will
# check a single $isofile and report such status.
#
# If $var_to_set is given and non-NULL, set the variable to the value of the
# `active' property of the struct associated with $isofile (an ISO_ENTRY
# structure defined in GLOBALS; usually NULL or `1') in-addition to returning
# true if the $isofile is active (and error status if inactive).
#
# Global variables required:
#
# 	NETBOOT_SRC	Path to boot image build-framework
#
check_one()
{
	local __isofile="$1" __var_to_set="$2"
	local __iso_filename="${__isofile##*/}"
	local __iso_name="${__iso_filename%.iso}"
	local __name

	f_str2varname "$__iso_name.${NETBOOT_SRC##*/}" __name
	local __active=
	f_struct isoentry_$__name && isoentry_$__name get active __active

	[ "$__var_to_set" ] && setvar "$__var_to_set" "$__active"
	[ "$__active" ] # Return status
}

# dialog_menu_main
#
# Display the dialog(1)-based application main menu.
#
# Global variables required:
#
# 	NETBOOT_SRC	Path to boot image build-framework
# 	ISOIMPORT_DIR	Where to find original ISO files for import
#
dialog_menu_main()
{
	local title="$DIALOG_TITLE"
	local btitle="$DIALOG_BACKTITLE"
	local prompt="$msg_pxe_boot_configuration_menu"
	[ "$USE_XDIALOG" ] && prompt="$xmsg_pxe_boot_configuration_menu"
	local menu_list= # Calculated below
	local defaultitem= # Calculated below
	local hline="$hline_arrows_tab_enter"

	#
	# Build the menu list of ISO entries
	#
	scan_iso_entries || return $?
	local i active label rootdir uri index=1 menu_list=
	for i in $( f_replaceall "$ISO_ENTRIES" "[$IFS]" "$NL" | sort ); do
		f_struct isoentry_$i || continue
		[ $index -lt ${#MENU_TAGS} ] || break

		isoentry_$i get active  active
		isoentry_$i get label   label
		isoentry_$i get rootdir rootdir
		isoentry_$i get uri     uri

		local mark=" "
		[ "$active" ] && mark="X"

		local tag
		tag=$( f_substr "$MENU_TAGS" $index 1 )
		setvar ISO_ENTRY$tag $i # For quick de-referencing

		f_shell_escape "$label" label
		menu_list="$menu_list
			'$tag [$mark]' '$label'
		" # END-QUOTE

		index=$(( $index + 1 ))
	done

	#
	# Handle the case of `no items'
	#
	if [ $index -eq 1 ]; then
		f_show_msg "$msg_no_iso_files_found_in_dir" "$ISOIMPORT_DIR"
		return $DIALOG_ESC # causes termination without saving
	fi

	local height width rows
	eval f_dialog_menu_size height width rows \
		\"\$title\"	\
		\"\$btitle\"	\
		\"\$prompt\"	\
		\"\$hline\"	\
		$menu_list

	# Obtain default-item from previously stored selection
	f_dialog_default_fetch defaultitem

	# The default-item may need changing based on state
	local defaultentry active
	f_getvar ISO_ENTRY${defaultitem%%[$IFS]*} defaultentry
	if [ "$defaultentry" ] && f_struct isoentry_$defaultentry; then
		isoentry_$defaultentry get active active
		case "$defaultitem" in
		*" [ ]"*) [ "$active" ] &&
		defaultitem="${defaultitem%% ? ?*} [X]${defaultitem#* ? ?}" ;;
		*" [X]"*) [ ! "$active" ] &&
		defaultitem="${defaultitem%% ?X?*} [ ]${defaultitem#* ?X?}" ;;
		esac
	fi

	local menu_choice
	# NB: Xdialog(1) compat flag is to get monospace font for
	#     simulating checkboxes in the menu list
	menu_choice=$( eval \
		${USE_XDIALOG:+XDIALOG_HIGH_DIALOG_COMPAT=1} $DIALOG \
		--title \"\$title\"                \
		--backtitle \"\$btitle\"           \
		--hline \"\$hline\"                \
		--keep-tite                        \
		--ok-label \"\$msg_select\"        \
		--cancel-label \"\$msg_save_exit\" \
		--default-item \"\$defaultitem\"   \
		--menu \"\$prompt\"                \
		$height $width $rows               \
		$menu_list                         \
		2>&1 >&$DIALOG_TERMINAL_PASSTHRU_FD
	)
	local retval=$?
	f_dialog_data_sanitize menu_choice
	f_dialog_menutag_store "$menu_choice"

	# Only update default-item on success
	[ $retval -eq $DIALOG_OK ] &&
		f_dialog_default_store "$menu_choice"

	return $retval
}

# read_template $file [$key1 $value1 ...]
#
# Display a $template_file with optional pre-processor macro definitions. The
# first argument is the template file. If additional arguments appear after
# $file, substitutions are made while printing the contents of $file. The pre-
# processor macro syntax is in the style of autoconf(1), for example:
#
# 	read_template $file "FOO" "BAR"
#
# will cause instances of "@FOO@" appearing in $file to be replaced with the
# text "BAR" before being printed to standard output.
#
read_template()
{
	local file="$1"
	shift 1 # file

	local output
	output=$( cat "$file" ) || return $?

	while [ $# -gt 0 ]; do
		local key="$1"
		export value="$2"
		output=$( echo "$output" |
			awk "{ gsub(/@$key@/, ENVIRON[\"value\"]); print }" )
		shift 2
	done

	echo "$output"
}

# save_iso_entries
#
# Save active ISO_ENTRIES in the PXE configuration menu, making them appear to
# the end PXE user on boot.
#
# Global variables required:
#
# 	USE_SMB		Set to non-NULL to use SMB instead of NFS
# 	SMB_CONF	Samba configuration file
# 	SMB_CONF_TEMPLATE
# 			Samba configuration file template
# 	MENU_CONF	syslinux menu configuration file
# 	MENU_CONF_TEMPLATE
# 			syslinux menu configuration file template
#
save_iso_entries()
{
	# Perform quick sanity check(s)
	if [ ! -f "$MENU_CONF_TEMPLATE" ]; then
		printf "$msg_no_such_file_or_directory\n" \
		       "$pgm" "$MENU_CONF_TEMPLATE" >&2
		return $FAILURE
	fi
	if [ "$USE_SMB" -a ! -f "$SMB_CONF_TEMPLATE" ]; then
		printf "$msg_no_such_file_or_directory\n" \
		       "$pgm" "$SMB_CONF_TEMPLATE" >&2
		return $FAILURE
	fi

	scan_iso_entries || return $?

	#
	# Update the syslinux PXE menu configuration file (via template)
	#
	local i tag active label uri index=1 output=
	for i in $( f_replaceall "$ISO_ENTRIES" "[$IFS]" "$NL" | sort ); do
		f_struct isoentry_$i || continue # Pedantic
		isoentry_$i get active  active
		isoentry_$i get label   label
		isoentry_$i get uri     uri
		[ "$active" ] || continue
		tag=$( f_substr "$MENU_TAGS" $index 1 )
		output="${output}LABEL $label
	MENU LABEL ^$tag $label
	MENU INDENT 1
	MENU CLEAR
	KERNEL memdisk
	APPEND iso raw initrd=http://$HTTP_SERVER$uri
		$NL" # END-QUOTE
		index=$(( $index + 1 ))
	done
	output="${output%$NL}"
	( read_template "$MENU_CONF_TEMPLATE" "TITLE" "$MENU_TITLE" \
		"ISO_ENTRIES" "$output" > "$MENU_CONF" ) || return $?
	echo ">>> $msg_successfully_updated_pxe_boot_configuration_file"

	#
	# Update the `smb.conf' file (if necessary; via template)
	#
	if [ "$USE_SMB" ]; then
		local i active label rootdir uri output=
		for i in $( f_replaceall "$ISO_ENTRIES" "[$IFS]" "$NL" | sort )
		do
			f_struct isoentry_$i || continue # Pedantic
			isoentry_$i get active  active
			isoentry_$i get rootdir rootdir
			[ "$active" ] || continue
			output="${output}[${rootdir##*/}]
	comment = pxe-config mount
	path = $rootdir
	guest ok = yes
	public = yes
	writeable = no
	read only = yes
			$NL" #END-QUOTE
		done
		output="${output%$NL}"
		( read_template "$SMB_CONF_TEMPLATE" "ISO_ENTRIES" "$output" \
			> "$SMB_CONF" ) || return $?
		echo ">>> $msg_successfully_updated_smb_configuration_file"
	fi

	return $SUCCESS
}

############################################################ MAIN

#
# Process command-line options
#
while getopts 123AachIilNnpqRsUuvX$GETOPTS_STDARGS flag; do
	case "$flag" in
	1) NO_IMAGE=1 NO_HTTP_ISO=1 NO_SAVE=1 ;;
	2) NO_SYNC=1 NO_HTTP_ISO=1 NO_SAVE=1 ;;
	3) NO_SYNC=1 NO_IMAGE=1 NO_SAVE=1 ;;
	A) ACT_ON_ALL=1 ;;
	a) ACT_ON_INACTIVE=1 ;;
	c) CHECK_ONLY=1 ;;
	h|\?) usage ;;
	I) NO_HTTP_ISO=1 ;;
	i) NO_IMAGE=1 ;;
	l) CHECK_ONLY=1 ACT_ON_ALL=1 QUIET= VERBOSE=1 ;;
	N) USE_SMB= ;;
	n) NO_SYNC=1 ;;
	p) ALWAYS_STAGE=1 ;;
	q) QUIET=1 ;;
	R) REMOVE=1 ;;
	s) USE_SMB=1 ;;
	U) NO_SYNC=1 NO_IMAGE=1 NO_HTTP_ISO=1 UPDATE_PXE=1 ;;
	u) NO_SAVE=1 ;;
	v) QUIET= VERBOSE=1 ;;
	X) USE_XDIALOG=1 ;;
	esac
done
shift $(( $OPTIND - 1 ))

#
# Get optional path to ISO file
#
ISO_FILE="$1"
[ "$ACT_ON_ALL" ] && ISO_FILE=

#
# Determine short-name of ISO and HTTP URI
#
iso_filename="${ISO_FILE##*/}"
iso_name="${iso_filename%.iso}"
uri="$ISOEXPORT_URI/$iso_name.${NETBOOT_SRC##*/}.iso"

#
# Process `check only' option (`-c')
#
if [ "$CHECK_ONLY" ]; then
	scan_iso_entries || die
	if [ "$ISO_FILE" ]; then
		check_one "$ISO_FILE" active
		if [ "$active" ]; then
			[ "$QUIET" ] || echo "$msg_active"
			exit $SUCCESS
		else
			[ "$QUIET" ] || echo "$msg_inactive"
			exit $FAILURE
		fi
		# Never reached
	elif [ "$ACT_ON_ALL" ]; then
		# Return true if all are active, otherwise die
		[ "$VERBOSE" ] && printf "%8s   %s\n" "STATUS" "FILE"
		status=$SUCCESS
		for ISO_FILE in "$ISOIMPORT_DIR"/*.iso; do
			[ -f "$ISO_FILE" ] || continue # no-match case
			# Check the name of the ISO file against filter
			echo "${ISO_FILE##*/}" | awk -v filter="$ISOFILTER" \
				'$0~filter{found++; exit}END{exit ! found}' ||
				continue # Skip if ISO doesn't match filter
			if ! check_one "$ISO_FILE"; then
				status=$FAILURE
				if [ "$VERBOSE" ]; then
					printf "%8s   %s\n" "$msg_inactive" \
					       "$ISO_FILE"
				else
					break
				fi
			else
				[ "$VERBOSE" ] && printf "%8s   %s\n" \
					"$msg_active" "$ISO_FILE"
			fi
		done
		[ "$VERBOSE" -o "$QUIET" ] && exit $status
		if [ $status -eq $SUCCESS ]; then
			echo "$msg_all_active"
		else
			echo "$msg_one_or_more_inactive"
		fi
		exit $status
		# Never reached
	elif [ "$ACT_ON_INACTIVE" ]; then
		# Return true if all are active, otherwise die
		[ "$VERBOSE" ] && printf "%8s   %s\n" "STATUS" "FILE"
		status=$SUCCESS
		for i in $ISO_ENTRIES; do
			f_struct isoentry_$i || continue # Pedantic
			isoentry_$i get active active
			[ "$active" ] && continue
			status=$FAILURE
			if [ "$VERBOSE" ]; then
				isoentry_$i get file file
				printf "%8s   %s\n" "$msg_inactive" "$file"
			else
				break
			fi
		done
		[ "$VERBOSE" -o "$QUIET" ] && exit $status
		if [ $status -eq $SUCCESS ]; then
			echo "$msg_all_active"
		else
			echo "$msg_one_or_more_inactive"
		fi
		exit $status
		# Never reached
	else
		# No ISO files
		exit $SUCCESS
	fi
	# Never reached
fi

#
# Become root via sudo(8) if necessary. To allow a group of users to do this
# without password, add the following line to sudoers(5):
#
# 	%pxe-config	ALL=(root) NOPASSWD: <path_to_this_file>
#
# Then add the user to the `pxe-config' group.
#
# NB: It's tempting to use bsdconfig(8)'s `mustberoot.subr' (providing the
#     f_become_root_via_sudo() function), but since we're 50% cmdline utility
#     and 50% dialog(1)/Xdialog(1) utility, let's stick to using sudo(8)
#     without an interface.
#
if [ "$( id -u )" != "0" ]; then
	if [ $ARGC -gt 0 ]; then
		echo "sudo $0 $ARGV"
		exec sudo "$0" $ARGV
	else
		echo "sudo $0"
		exec sudo "$0"
	fi
	exit $? # Never reached unless error
fi

#
# Process `Remove' option (`-R')
#
if [ "$REMOVE" ]; then
	scan_iso_entries || die
	if [ "$ISO_FILE" ]; then
		remove_one "$ISO_FILE"
	elif [ "$ACT_ON_ALL" ]; then
		for ISO_FILE in "$ISOIMPORT_DIR"/*.iso; do
			[ -f "$ISO_FILE" ] || continue # no-match case
			# Check the name of the ISO file against filter
			echo "${ISO_FILE##*/}" | awk -v filter="$ISOFILTER" \
				'$0~filter{found++; exit}END{exit ! found}' ||
				continue # Skip if ISO doesn't match filter
			remove_one "$ISO_FILE"
		done
	elif [ "$ACT_ON_INACTIVE" ]; then
		for i in $ISO_ENTRIES; do
			f_struct isoentry_$i || continue # Pedantic
			isoentry_$i get active active
			[ "$active" ] && continue
			isoentry_$i get file file
			remove_one "$file"
		done
	fi
	exit $SUCCESS
fi

#
# Check environment sanity before continuing further
#
[ "$NO_SYNC" -a ! "$ALWAYS_STAGE" ] || f_have rsync ||
	die "$msg_no_such_file_or_directory" "$pgm" "rsync"
[ -d "$NETBOOT_SRC" ] ||
	die "$msg_no_such_file_or_directory" "$pgm" "$NETBOOT_SRC"
f_have mkisofs ||
	die "$msg_no_such_file_or_directory" "$pgm" "mkisofs"

#
# If given the `-U' option, update PXE files and exit
#
if [ "$UPDATE_PXE" ]; then
	if [ "$QUIET" ]; then
		f_quietly save_iso_entries || die
	else
		save_iso_entries
	fi

	#
	# Landmark for the user
	#
	[ "$QUIET" ] || echo "Success!"
	exit $SUCCESS
fi

#
# If given an ISO file or told to act on all, operate on it/them
#
if [ "$ISO_FILE" ]; then
	if process_one "$ISO_FILE"; then
		rm -f "$HTTP_DATA$uri.ignore"
	else
		touch "$HTTP_DATA$uri.ignore"
		die
	fi
elif [ "$ACT_ON_ALL" ]; then
	status=$SUCCESS
	for ISO_FILE in "$ISOIMPORT_DIR"/*.iso; do
		[ -f "$ISO_FILE" ] || continue # no-match case
		# Check the name of the ISO file against filter
		echo "${ISO_FILE##*/}" | awk -v filter="$ISOFILTER" \
			'$0~filter{found++; exit}END{exit ! found}' ||
			continue # Skip if ISO doesn't match filter
		iso_filename="${ISO_FILE##*/}"
		iso_name="${iso_filename%.iso}"
		uri="$ISOEXPORT_URI/$iso_name.${NETBOOT_SRC##*/}.iso"
		if process_one "$ISO_FILE"; then
			rm -f "$HTTP_DATA$uri.ignore"
		else
			touch "$HTTP_DATA$uri.ignore"
			status=$FAILURE

			# Cleanup required from previous failure?
			[ "$ISO_CLEAN" ] && f_quietly eval "$ISO_CLEAN"
			[ "$MD_CLEAN" ] && f_quietly eval "$MD_CLEAN"
			ISO_CLEAN= MD_CLEAN=
		fi
	done
	[ $status -eq $SUCCESS ] || f_err "!!! $msg_some_items_failed\n"
elif [ "$ACT_ON_INACTIVE" ]; then
	scan_iso_entries || die
	status=$SUCCESS
	for i in $ISO_ENTRIES; do
		f_struct isoentry_$i || continue # Pedantic
		isoentry_$i get active active
		[ "$active" ] && continue
		isoentry_$i get file file
		isoentry_$i get uri uri
		if process_one "$file"; then
			rm -f "$HTTP_DATA$uri.ignore"
		else
			touch "$HTTP_DATA$uri.ignore"
			status=$FAILURE

			# Cleanup required from previous failure?
			[ "$ISO_CLEAN" ] && f_quietly eval "$ISO_CLEAN"
			[ "$MD_CLEAN" ] && f_quietly eval "$MD_CLEAN"
			ISO_CLEAN= MD_CLEAN=
		fi
	done
	[ $status -eq $SUCCESS ] || f_err "!!! $msg_some_items_failed\n"
fi

#
# If given an ISO file or told to act on all/some, save PXE files and exit
#
# NB: In other words, if we weren't given any command-line actions, exit here
#     before reaching the interactive dialog(1)/Xdialog(1) menu invoked when
#     executed without ISO arguments.
#
if [ "$ISO_FILE" -o "$ACT_ON_ALL" -o "$ACT_ON_INACTIVE" ]; then
	#
	# Update the PXE boot menu and SMB share configuration
	#
	if [ ! "$NO_SAVE" ]; then
		if [ "$QUIET" ]; then
			f_quietly save_iso_entries || die
		else
			save_iso_entries
		fi
	fi

	#
	# Landmark for the user
	#
	[ "$QUIET" ] || echo "Success!"
	exit $SUCCESS
fi

#
# Initialize the dialog library (optionally automatically enabling X11)
#
if [ "$DISPLAY" -a ! "$USE_XDIALOG" ]; then
	echo "$msg_enabling_x11_mode"
	ARGV="-X" ARGC=1 f_dialog_init
else
	f_dialog_init
fi

#
# Launch application main menu
#
while :; do
	# Cleanup required from previous failure?
	[ "$ISO_CLEAN" ] && f_quietly eval "$ISO_CLEAN"
	[ "$MD_CLEAN" ] && f_quietly eval "$MD_CLEAN"
	ISO_CLEAN= MD_CLEAN=

	# Launch the main menu and get the user's choice
	dialog_menu_main
	retval=$?
	f_dialog_menutag_fetch mtag
	f_dprintf "retval=%u mtag=[%s]" $retval "$mtag"

	# Exit if the user pressed ESC
	[ $retval -eq $DIALOG_ESC ] && break # to success

	# Save active configurations
	if [ $retval -ne $DIALOG_OK ]; then
		f_dialog_info "$msg_saving_pxe_configuration"
		if ! err=$( save_iso_entries 2>&1 > /dev/null ); then
			f_show_msg "%s" "$err"
			continue
		fi
		break # to success
	fi

	# de-reference the tag into struct handle
	f_getvar ISO_ENTRY${mtag%%[$IFS]*} i
	f_struct isoentry_$i || f_show_msg "Invalid selection?!"

	isoentry_$i get active  active
	isoentry_$i get label   label
	isoentry_$i get rootdir rootdir
	isoentry_$i get uri     uri

	#
	# Make it inactive
	#
	if [ "$active" ]; then
		touch "$HTTP_DATA$uri.ignore"
		continue
	fi

	#
	# Make it active
	#
	rm -f "$HTTP_DATA$uri.ignore"
	ISO_FILE="$ISOIMPORT_DIR/${label%.${NETBOOT_SRC##*/}*}.iso"

	# If $rootdir appears incomplete, re-unpack
	if [ ! "$NO_SYNC" ] &&
	   [ "$ALWAYS_STAGE" -o ! -f "$rootdir/etc/rc" ]
	then
		if [ "$USE_XDIALOG" ]; then
			err=$( unpack_iso "$ISO_FILE" 2>&1 > /dev/null ) |
				f_xdialog_info "$msg_unpacking ${ISO_FILE##*/}"
			[ "$err" ] && {
				touch "$HTTP_DATA$uri.ignore"
				f_yesno "%s\n\n$abort_remaining" "$err" &&
					continue
			}
		else
			f_dialog_info "$msg_unpacking ${ISO_FILE##*/}"
			if ! err=$( unpack_iso "$ISO_FILE" 2>&1 > /dev/null )
			then
				touch "$HTTP_DATA$uri.ignore"
				f_show_msg "%s" "$err"
				continue
			fi
		fi
	fi

	# Check for interim boot image
	if [ ! "$NO_IMAGE" ] &&
	   [ "$ALWAYS_STAGE" -o ! -f "$rootdir/boot/${NETBOOT_SRC##*/}.gz" ]
	then
		if [ "$USE_XDIALOG" ]; then
			err=$( create_netboot_image "$ISO_FILE" \
				2>&1 > /dev/null ) | f_xdialog_info \
				"$msg_creating ${NETBOOT_SRC##*/}.gz"
			[ "$err" ] && {
				touch "$HTTP_DATA$uri.ignore"
				f_yesno "%s\n\n$abort_remaining" "$err" &&
					continue
			}
		else
			f_dialog_info "$msg_creating ${NETBOOT_SRC##*/}.gz"
			if ! err=$( create_netboot_image "$ISO_FILE" \
				2>&1 > /dev/null )
			then
				touch "$HTTP_DATA$uri.ignore"
				f_show_msg "%s" "$err"
				continue
			fi
		fi
	fi

	# If $uri to the boot image does not exist, create it
	if [ ! "$NO_HTTP_ISO" ] && [ "$ALWAYS_STAGE" -o ! -e "$HTTP_DATA$uri" ]
	then
		if [ "$USE_XDIALOG" ]; then
			err=$( create_netboot_iso "$ISO_FILE" \
				2>&1 > /dev/null ) | f_xdialog_info \
				"$msg_creating ${uri##*/}"
			[ "$err" ] && {
				touch "$HTTP_DATA$uri.ignore"
				f_yesno "%s\n\n$abort_remaining" "$err" &&
				continue
			}
		else
			f_dialog_info "$msg_creating ${uri##*/}"
			if ! err=$( create_netboot_iso "$ISO_FILE" \
				2>&1 > /dev/null )
			then
				touch "$HTTP_DATA$uri.ignore"
				f_show_msg "%s" "$err"
				continue
			fi
		fi
	fi
done

exit $SUCCESS

################################################################################
# END
################################################################################
