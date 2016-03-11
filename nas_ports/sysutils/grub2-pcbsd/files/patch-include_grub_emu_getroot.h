--- include/grub/emu/getroot.h.orig	2015-01-23 02:27:45 UTC
+++ include/grub/emu/getroot.h
@@ -44,6 +44,8 @@ char *grub_util_get_grub_dev (const char
 #if defined (__FreeBSD__) || defined(__FreeBSD_kernel__)
 void grub_util_follow_gpart_up (const char *name, grub_disk_addr_t *off_out,
 				char **name_out);
+int grub_util_check_geom_label(const char *name);
+const char *grub_util_convert_geom_label_to_dev (const char *name, int *full_path);
 #endif
 
 #include <sys/stat.h>
