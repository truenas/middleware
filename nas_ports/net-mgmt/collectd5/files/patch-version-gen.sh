--- version-gen.sh.orig	2016-09-11 08:10:25 UTC
+++ version-gen.sh
@@ -1,13 +1,2 @@
 #!/bin/sh
-
-DEFAULT_VERSION="5.6.0.git"
-
-if [ -d .git ]; then
-	VERSION="`git describe --dirty=+ --abbrev=7 2> /dev/null | grep collectd | sed -e 's/^collectd-//' -e 's/-/./g'`"
-fi
-
-if test -z "$VERSION"; then
-	VERSION="$DEFAULT_VERSION"
-fi
-
-printf "%s" "$VERSION"
+echo -n '5.6.0.git'
