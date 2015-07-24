--- grub-core/disk/geli.c.orig	2014-12-30 11:08:32.000000000 -0500
+++ grub-core/disk/geli.c	2015-01-13 13:42:46.758595608 -0500
@@ -225,7 +225,7 @@
 
   /* Look for GELI magic sequence.  */
   if (grub_memcmp (header->magic, GELI_MAGIC, sizeof (GELI_MAGIC))
-      || grub_le_to_cpu32 (header->version) > 5
+      || grub_le_to_cpu32 (header->version) > 7
       || grub_le_to_cpu32 (header->version) < 1)
     grub_util_error ("%s", _("wrong ELI magic or version"));
 
@@ -265,7 +265,7 @@
 
   /* Look for GELI magic sequence.  */
   if (grub_memcmp (header.magic, GELI_MAGIC, sizeof (GELI_MAGIC))
-      || grub_le_to_cpu32 (header.version) > 5
+      || grub_le_to_cpu32 (header.version) > 7
       || grub_le_to_cpu32 (header.version) < 1)
     {
       grub_dprintf ("geli", "wrong magic %02x\n", header.magic[0]);
@@ -401,6 +401,7 @@
   grub_uint8_t geomkey[GRUB_CRYPTO_MAX_MDLEN];
   grub_uint8_t verify_key[GRUB_CRYPTO_MAX_MDLEN];
   grub_uint8_t zero[GRUB_CRYPTO_MAX_CIPHER_BLOCKSIZE];
+  grub_uint8_t geli_cipher_key[64];
   char passphrase[MAX_PASSPHRASE] = "";
   unsigned i;
   gcry_err_code_t gcry_err;
@@ -440,6 +441,9 @@
   if (!grub_password_get (passphrase, MAX_PASSPHRASE))
     return grub_error (GRUB_ERR_BAD_ARGUMENT, "Passphrase not supplied");
 
+  /* Set the GELI passphrase to GRUB env, for passing to FreeBSD kernel */
+  grub_env_set ("gelipassphrase", passphrase);
+
   /* Calculate the PBKDF2 of the user supplied passphrase.  */
   if (grub_le_to_cpu32 (header.niter) != 0)
     {
@@ -524,6 +528,19 @@
 	continue;
       grub_printf_ (N_("Slot %d opened\n"), i);
 
+      if (grub_le_to_cpu32 (header.version) >= 7)
+        {
+          /* GELI >=7 uses the cipher_key */
+	  grub_memcpy (geli_cipher_key, candidate_key.cipher_key,
+		sizeof (candidate_key.cipher_key));
+        }
+      else
+        {
+          /* GELI <=6 uses the iv_key */
+	  grub_memcpy (geli_cipher_key, candidate_key.iv_key,
+		sizeof (candidate_key.iv_key));
+        }
+
       /* Set the master key.  */
       if (!dev->rekey)
 	{
@@ -540,13 +557,13 @@
 	  grub_size_t real_keysize = keysize;
 	  if (grub_le_to_cpu16 (header.alg) == 0x16)
 	    real_keysize *= 2;
-	  /* For a reason I don't know, the IV key is used in rekeying.  */
-	  grub_memcpy (dev->rekey_key, candidate_key.iv_key,
-		       sizeof (candidate_key.iv_key));
+
+	  grub_memcpy (dev->rekey_key, geli_cipher_key,
+		       sizeof (geli_cipher_key));
 	  dev->rekey_derived_size = real_keysize;
 	  dev->last_rekey = -1;
 	  COMPILE_TIME_ASSERT (sizeof (dev->rekey_key)
-			       >= sizeof (candidate_key.iv_key));
+		       >= sizeof (geli_cipher_key));
 	}
 
       dev->iv_prefix_len = sizeof (candidate_key.iv_key);
