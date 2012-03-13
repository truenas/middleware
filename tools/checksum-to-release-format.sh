#!/bin/sh
#
# Script for producing checksums in the format:
#
# Filename:
# foo
# SHA256 Hash:
# foo-hash
#
# usage:
#	checksum-to-release-format.sh os-base/amd64
#	checksum-to-release-format.sh plugins/firefly/amd64 firefly
#
# XXX: this should probably be pushed into end2end-build.sh as it has more
# brains as far as what needs to be built than this script does.
#

set -u
avatar_component_target=$1
component_branding=${2:-FreeNAS}

sha256 $avatar_component_target/$component_branding-* | \
	grep -v 'sha256.txt' | \
	sed -e 's/SHA256 (//' -e 's/) = / /g' -e 's/.*\///g' | \
while read fname sha256sum; do
	cat <<EOF
Filename:
$fname
SHA256 Hash:
$sha256sum

EOF
done
