diff --git grub-core/loader/i386/bsd.c grub-core/loader/i386/bsd.c
index 8f691e0..8c7decd 100644
--- grub-core/loader/i386/bsd.c
+++ grub-core/loader/i386/bsd.c
@@ -415,11 +415,14 @@ grub_freebsd_add_meta_module (const char *filename, const char *type,
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
 
