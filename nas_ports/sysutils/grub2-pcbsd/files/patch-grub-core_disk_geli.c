--- grub-core/disk/geli.c.orig	2015-01-30 16:34:55 UTC
+++ grub-core/disk/geli.c
@@ -445,6 +445,9 @@ recover_key (grub_disk_t source, grub_cr
   if (!grub_password_get (passphrase, MAX_PASSPHRASE))
     return grub_error (GRUB_ERR_BAD_ARGUMENT, "Passphrase not supplied");
 
+  /* Set the GELI passphrase to GRUB env, for passing to FreeBSD kernel */
+  grub_env_set ("gelipassphrase", passphrase);
+
   /* Calculate the PBKDF2 of the user supplied passphrase.  */
   if (grub_le_to_cpu32 (header.niter) != 0)
     {
