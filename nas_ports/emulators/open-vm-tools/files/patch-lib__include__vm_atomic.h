--- lib/include/vm_atomic.h.orig	2013-09-23 17:51:10.000000000 +0200
+++ lib/include/vm_atomic.h	2015-02-04 16:28:59.372337000 +0100
@@ -2460,7 +2460,8 @@
                                       && 8 * sizeof (out) == size             \
                                       && 8 * sizeof (cast) == size            \
                                          ? 1 : -1 };                          \
-      typedef char AssertOnCompileFailed[AssertOnCompileMisused];             \
+      typedef char AssertOnCompileFailed[AssertOnCompileMisused]              \
+         __attribute__((__unused__));                                         \
    }                                                                          \
                                                                               \
                                                                               \
