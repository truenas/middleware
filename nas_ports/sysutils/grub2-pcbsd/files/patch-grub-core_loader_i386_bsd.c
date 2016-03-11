--- grub-core/loader/i386/bsd.c.orig	2015-01-30 16:34:55 UTC
+++ grub-core/loader/i386/bsd.c
@@ -416,11 +416,14 @@ grub_freebsd_add_meta_module (const char
 			      grub_addr_t addr, grub_uint32_t size)
 {
   const char *name;
-  name = grub_strrchr (filename, '/');
+ /* Don't strip the full path, some FreeBSD functionality, such
+  * as dtrace, rely on this. Instead only strip out the portion after ZFS @ sign */
+  name = grub_strrchr (filename, '@');
   if (name)
     name++;
   else
     name = filename;
+
   if (grub_strcmp (type, "/boot/zfs/zpool.cache") == 0)
     name = "/boot/zfs/zpool.cache";
 
