--- etc/afpd/desktop.c	2016-06-06 04:21:51.000000000 -0700
+++ etc/afpd/desktop.c	2016-10-19 20:19:05.040995507 -0700
@@ -51,6 +51,10 @@
     struct dirent	*deskp, *subp;
     DIR			*desk, *sub;
 
+	if (vol->v_obj->options.flags & OPTION_ACL2MODE) {
+		return 0;
+	}
+
     if (!dir_rx_set(mode)) {
         /* want to remove read and search access to owner it will screw the volume */
         return -1 ;
