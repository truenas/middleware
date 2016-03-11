--- grub-core/osdep/unix/getroot.c.orig	2015-06-03 14:54:01 UTC
+++ grub-core/osdep/unix/getroot.c
@@ -507,6 +507,12 @@ grub_guess_root_devices (const char *dir
   if (!os_dev)
     os_dev = find_root_devices_from_libzfs (dir);
 
+#if defined(__FreeBSD__) || defined(__FreeBSD_kernel__)
+  if (os_dev)
+    if ( grub_util_check_geom_label(os_dev) )
+      os_dev = grub_util_convert_geom_label_to_dev (os_dev + sizeof ("/dev/") - 1, 1);
+#endif
+
   if (os_dev)
     {
       char **cur;
