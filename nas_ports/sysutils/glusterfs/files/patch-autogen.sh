--- autogen.sh.orig	2014-06-22 22:24:25.000000000 -0700
+++ autogen.sh	2014-06-23 12:31:09.000000000 -0700
@@ -4,84 +4,13 @@
 echo ... GlusterFS autogen ...
 echo
 
-## Check all dependencies are present
-MISSING=""
-
-# Check for aclocal
-env aclocal --version > /dev/null 2>&1
-if [ $? -eq 0 ]; then
-  ACLOCAL=aclocal
-else
-  MISSING="$MISSING aclocal"
-fi
-
-# Check for autoconf
-env autoconf --version > /dev/null 2>&1
-if [ $? -eq 0 ]; then
-  AUTOCONF=autoconf
-else
-  MISSING="$MISSING autoconf"
-fi
-
-# Check for autoheader
-env autoheader --version > /dev/null 2>&1
-if [ $? -eq 0 ]; then
-  AUTOHEADER=autoheader
-else
-  MISSING="$MISSING autoheader"
-fi
-
-# Check for automake
-env automake --version > /dev/null 2>&1
-if [ $? -eq 0 ]; then
-  AUTOMAKE=automake
-else
-  MISSING="$MISSING automake"
-fi
-
-# Check for libtoolize or glibtoolize
-env libtoolize --version > /dev/null 2>&1
-if [ $? -eq 0 ]; then
-  # libtoolize was found, so use it
-  TOOL=libtoolize
-else
-  # libtoolize wasn't found, so check for glibtoolize
-  env glibtoolize --version > /dev/null 2>&1
-  if [ $? -eq 0 ]; then
-    TOOL=glibtoolize
-  else
-    MISSING="$MISSING libtoolize/glibtoolize"
-  fi
-fi
-
-# Check for tar
-env tar -cf /dev/null /dev/null > /dev/null 2>&1
-if [ $? -ne 0 ]; then
-  MISSING="$MISSING tar"
-fi
-
-## If dependencies are missing, warn the user and abort
-if [ "x$MISSING" != "x" ]; then
-  echo "Aborting."
-  echo
-  echo "The following build tools are missing:"
-  echo
-  for pkg in $MISSING; do
-    echo "  * $pkg"
-  done
-  echo
-  echo "Please install them and try again."
-  echo
-  exit 1
-fi
-
 ## Do the autogeneration
 echo Running ${ACLOCAL}...
 $ACLOCAL -I ./contrib/aclocal
 echo Running ${AUTOHEADER}...
 $AUTOHEADER
-echo Running ${TOOL}...
-$TOOL --automake --copy --force
+echo Running ${LIBTOOLIZE}...
+$LIBTOOLIZE --automake --copy --force
 echo Running ${AUTOCONF}...
 $AUTOCONF
 echo Running ${AUTOMAKE}...
