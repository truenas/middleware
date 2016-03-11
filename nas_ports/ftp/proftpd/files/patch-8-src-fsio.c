--- src/fsio.c.orig	2010-04-12 21:00:00.000000000 +0200
+++ src/fsio.c	2011-12-29 21:51:33.844925577 +0100
@@ -50,6 +50,10 @@
 # include <acl/libacl.h>
 #endif
 
+#if defined(__FreeBSD__)
+#include <dlfcn.h>
+#endif
+
 typedef struct fsopendir fsopendir_t;
 
 struct fsopendir {
@@ -284,7 +288,30 @@
 #endif
 }
 
+#if defined(__FreeBSD__)
+static int
+enter_freebsd_restricted_mode()
+{
+  typedef void frmode_t();
+  frmode_t *frmode;
+
+  frmode = (frmode_t *)dlfunc(
+    RTLD_NEXT, "__FreeBSD_libc_enter_restricted_mode");
+  if (frmode == NULL) {
+    pr_log_pri(PR_LOG_ERR,
+      "error: FreeBSD with vulnerable chroot (FreeBSD-SA-11:07.chroot)");
+    return 1;
+  }
+  frmode();
+  return 0;
+}
+#endif
+
 static int sys_chroot(pr_fs_t *fs, const char *path) {
+#if defined(__FreeBSD__)
+  if (enter_freebsd_restricted_mode() != 0)
+    return -1;
+#endif
   if (chroot(path) < 0)
     return -1;
 
