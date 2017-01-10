--- modules/freebsd/vmhgfs/os.c.orig
+++ modules/freebsd/vmhgfs/os.c
@@ -647,7 +647,7 @@
 		 OS_THREAD_T *newThread)   // OUT
 {
    return compat_kthread_create(function, parameter,
-                                newThread, 0, 0, threadName);
+                                newThread, 0, 0, "%s", threadName);
 }
 
 
