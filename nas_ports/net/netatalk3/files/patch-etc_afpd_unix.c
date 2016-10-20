--- etc/afpd/unix.c	2016-06-06 04:21:51.000000000 -0700
+++ etc/afpd/unix.c	2016-10-19 20:18:58.179838026 -0700
@@ -234,7 +234,7 @@
     mode |= vol->v_dperm | DIRBITS;
     mode &= ~vol->v_umask;
 
-    if (dir_rx_set(mode)) {
+    if (dir_rx_set(mode) && !(vol->v_obj->options.flags & OPTION_ACL2MODE)) {
     	/* extending right? dir first then .AppleDouble in rf_setdirmode */
         if (ochmod(name, mode, NULL,
                    vol_syml_opt(vol) | vol_chmod_opt(vol)
@@ -244,7 +244,7 @@
     if (vol->vfs->vfs_setdirunixmode(vol, name, mode, NULL) < 0) {
         return  -1 ;
     }
-    if (!dir_rx_set(mode)) {
+    if (!dir_rx_set(mode) && !(vol->v_obj->options.flags & OPTION_ACL2MODE)) {
         if (ochmod(name, mode, NULL,
                    vol_syml_opt(vol) | vol_chmod_opt(vol)
                 ) < 0)
