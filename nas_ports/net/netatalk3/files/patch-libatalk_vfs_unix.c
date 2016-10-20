--- libatalk/vfs/unix.c	2016-06-06 04:21:51.000000000 -0700
+++ libatalk/vfs/unix.c	2016-10-19 20:15:45.864161185 -0700
@@ -38,6 +38,10 @@
     struct stat sb;
     mode_t mask = S_IRWXU | S_IRWXG | S_IRWXO;  /* rwx for owner group and other, by default */
 
+	if (vol->v_obj->options.flags & OPTION_ACL2MODE) {
+		return 0;
+	}
+
     if (!st) {
         if (lstat(name, &sb) != 0)
             return -1;
