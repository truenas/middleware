--- deps/v8/src/log-utils.h.orig	2016-10-19 22:02:04 UTC
+++ deps/v8/src/log-utils.h
@@ -9,6 +9,9 @@
 
 #include <cstdarg>
 
+#include <cstdio>
+#include <cstdarg>
+
 #include "src/allocation.h"
 #include "src/base/platform/mutex.h"
 #include "src/flags.h"
