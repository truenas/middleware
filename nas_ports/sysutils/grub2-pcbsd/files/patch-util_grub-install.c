--- util/grub-install.c.orig	2015-06-03 14:54:01 UTC
+++ util/grub-install.c
@@ -236,7 +236,16 @@ argp_parser (int key, char *arg, struct 
     case ARGP_KEY_ARG:
       if (install_device)
 	grub_util_error ("%s", _("More than one install device?"));
+#if defined (__FreeBSD__) || defined (__FreeBSD_kernel__)
+    /* Check if passing a FreeBSD geom label */
+    if ( grub_util_check_geom_label(arg) )
+      install_device = \
+        xstrdup(grub_util_convert_geom_label_to_dev (arg + sizeof ("/dev/") - 1, 1));
+    else
+      install_device = xstrdup (arg);
+#else
       install_device = xstrdup (arg);
+#endif
       return 0;
 
     default:
