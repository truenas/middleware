--- libatalk/vfs/vfs.c	2016-06-06 04:21:51.000000000 -0700
+++ libatalk/vfs/vfs.c	2016-10-19 20:19:30.277014599 -0700
@@ -171,7 +171,7 @@
 {
     const char *adouble = vol->ad_path(name, ADFLAGS_DIR );
 
-    if (dir_rx_set(mode)) {
+    if (dir_rx_set(mode) && !(vol->v_obj->options.flags & OPTION_ACL2MODE)) {
         if (ochmod(ad_dir(adouble),
                    (DIRBITS | mode) & ~vol->v_umask,
                    st,
@@ -183,7 +183,7 @@
     if (adouble_setfilmode(vol, vol->ad_path(name, ADFLAGS_DIR ), mode, st) < 0) 
         return -1;
 
-    if (!dir_rx_set(mode)) {
+    if (!dir_rx_set(mode) && !(vol->v_obj->options.flags & OPTION_ACL2MODE)) {
         if (ochmod(ad_dir(adouble),
                    (DIRBITS | mode) & ~vol->v_umask,
                    st,
@@ -219,7 +219,7 @@
     const char  *adouble = vol->ad_path(name, ADFLAGS_DIR );
     const char  *adouble_p = ad_dir(adouble);
 
-    if (dir_rx_set(mode)) {
+    if (dir_rx_set(mode) && !(vol->v_obj->options.flags & OPTION_ACL2MODE)) {
         if (ochmod(ad_dir(adouble),
                    (DIRBITS | mode) & ~vol->v_umask,
                    st,
@@ -231,7 +231,7 @@
     if (for_each_adouble("setdirmode", adouble_p, setdirmode_adouble_loop, vol, &hf_mode, 0))
         return -1;
 
-    if (!dir_rx_set(mode)) {
+    if (!dir_rx_set(mode) && !(vol->v_obj->options.flags & OPTION_ACL2MODE)) {
         if (ochmod(ad_dir(adouble),
                    (DIRBITS | mode) & ~vol->v_umask,
                    st,
