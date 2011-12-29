#!/bin/sh

sha256 obj.*/FreeNAS-* | grep -v 'sha256.txt' | sed -e 's/obj.*\///g' -e 's/) = / /g' -e 's/SHA256 (//' | \
while read fname sha256sum; do
	cat <<EOF
Filename:
$fname
SHA256 Hash:
$sha256sum

EOF
done
