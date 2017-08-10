--- src/common.c.orig	2017-01-22 19:49:22 UTC
+++ src/common.c
@@ -1111,6 +1111,16 @@ long get_system_cpus(void) {
         }
 
         return processors;
+    #elif __FreeBSD__
+        int32_t tmp_processors;
+
+        if (unlikely(GETSYSCTL("hw.ncpu", tmp_processors))) {
+            error("Assuming system has %d processors.", processors);
+        } else {
+            processors = tmp_processors;
+        }
+
+        return processors;
     #else
 
     char filename[FILENAME_MAX + 1];
@@ -1153,6 +1163,17 @@ pid_t get_system_pid_max(void) {
         // we use the number defined in bsd/sys/proc_internal.h in XNU sources
         pid_max = 99999;
         return pid_max;
+    #elif __FreeBSD__
+        int32_t tmp_pid_max;
+
+        if (unlikely(GETSYSCTL("kern.pid_max", tmp_pid_max))) {
+            pid_max = 99999;
+            error("Assuming system's maximum pid is %d.", pid_max);
+        } else {
+            pid_max = tmp_pid_max;
+        }
+
+        return pid_max;
     #else
 
     char filename[FILENAME_MAX + 1];
