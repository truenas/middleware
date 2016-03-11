--- util/grub-probe.c.orig	2015-06-03 14:54:01 UTC
+++ util/grub-probe.c
@@ -805,7 +805,16 @@ argp_parser (int key, char *arg, struct 
 
     case ARGP_KEY_ARG:
       assert (arguments->ndevices < arguments->device_max);
+#if defined (__FreeBSD__) || defined (__FreeBSD_kernel__)
+    /* Check if passing a FreeBSD geom label */
+    if ( grub_util_check_geom_label(arg) )
+      arguments->devices[arguments->ndevices++] = \
+	xstrdup(grub_util_convert_geom_label_to_dev (arg + sizeof ("/dev/") - 1, 1));
+    else
+      arguments->devices[arguments->ndevices++] = xstrdup(arg);
+#else
       arguments->devices[arguments->ndevices++] = xstrdup(arg);
+#endif
       break;
 
     default:
