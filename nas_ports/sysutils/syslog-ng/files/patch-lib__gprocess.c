--- lib/gprocess.c.orig	2014-07-17 10:12:50 UTC
+++ lib/gprocess.c
@@ -46,6 +46,10 @@
 #include <pwd.h>
 #include <grp.h>
 
+#include <err.h>
+#include <inttypes.h>
+#include <libutil.h>
+
 #if ENABLE_LINUX_CAPS
 #  include <sys/capability.h>
 #  include <sys/prctl.h>
@@ -125,6 +129,7 @@
   gint fd_limit_min;
   gint check_period;
   gboolean (*check_fn)(void);
+  struct pidfh *pfh;
 } process_opts =
 {
   .mode = G_PM_SAFE_BACKGROUND,
@@ -140,7 +145,8 @@
   .check_period = -1,
   .check_fn = NULL,
   .uid = -1,
-  .gid = -1
+  .gid = -1,
+  .pfh = NULL
 };
 
 #if ENABLE_SYSTEMD
@@ -721,6 +727,9 @@
 static void
 g_process_write_pidfile(pid_t pid)
 {
+#if defined(__FreeBSD__)
+  pidfile_write(process_opts.pfh);
+#else
   gchar buf[256];
   const gchar *pidfile;
   FILE *fd;
@@ -736,7 +745,7 @@
     {
       g_process_message("Error creating pid file; file='%s', error='%s'", pidfile, g_strerror(errno));
     }
-  
+#endif
 }
 
 /**
@@ -747,6 +756,9 @@
 static void
 g_process_remove_pidfile(void)
 {
+#if defined(__FreeBSD__)
+  pidfile_remove(process_opts.pfh);
+#else
   gchar buf[256];
   const gchar *pidfile;
 
@@ -756,6 +768,7 @@
     {
       g_process_message("Error removing pid file; file='%s', error='%s'", pidfile, g_strerror(errno));
     }
+#endif
 }
 
 /**
@@ -1259,11 +1272,28 @@
 g_process_start(void)
 {
   pid_t pid;
-  
+
+  gchar buf[256];
+  const gchar *pidfile;
+  FILE *fd;
+
+  pidfile = g_process_format_pidfile_name(buf, sizeof(buf));
+  process_opts.pfh = pidfile_open(pidfile, 0600, &pid);
+  if (process_opts.pfh == NULL) {
+	if (errno == EEXIST) {
+		errx(EXIT_FAILURE, "Daemon already running, pid: %jd.",
+		    (intmax_t)pid);
+		/* If we cannot create pidfile from other reasons, only warn. */
+		warn("Cannot open or create pidfile");
+	}
+  }
+
   g_process_detach_tty();
   g_process_change_limits();
   g_process_resolve_names();
-  
+
+  pidfile_write(process_opts.pfh);
+
   if (process_opts.mode == G_PM_BACKGROUND)
     {
       /* no supervisor, sends result to startup process directly */
@@ -1386,6 +1416,9 @@
   if (process_kind != G_PK_STARTUP)
     g_process_send_result(ret_num);
     
+
+  pidfile_remove(process_opts.pfh);
+
   if (may_exit)
     {
       exit(ret_num);
