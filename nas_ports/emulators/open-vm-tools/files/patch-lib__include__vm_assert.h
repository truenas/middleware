--- lib/include/vm_assert.h.orig	2013-09-23 17:51:10.000000000 +0200
+++ lib/include/vm_assert.h	2015-02-04 15:55:56.011187000 +0100
@@ -363,7 +363,8 @@
 #define ASSERT_ON_COMPILE(e) \
    do { \
       enum { AssertOnCompileMisused = ((e) ? 1 : -1) }; \
-      typedef char AssertOnCompileFailed[AssertOnCompileMisused]; \
+      typedef char AssertOnCompileFailed[AssertOnCompileMisused] \
+         __attribute__((__unused__)); \
    } while (0)
 
 
