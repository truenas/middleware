diff --git src/util/crypto/nss/nss_sha512crypt.c src/util/crypto/nss/nss_sha512crypt.c
index 9fedd5e..90192ac 100644
--- src/util/crypto/nss/nss_sha512crypt.c
+++ src/util/crypto/nss/nss_sha512crypt.c
@@ -29,6 +29,12 @@
 #include <sechash.h>
 #include <pk11func.h>
 
+static void *
+mempcpy (void *dest, const void *src, size_t n)
+{
+  return (char *) memcpy (dest, src, n) + n;
+}
+
 /* Define our magic string to mark salt for SHA512 "encryption" replacement. */
 const char sha512_salt_prefix[] = "$6$";
 #define SALT_PREF_SIZE (sizeof(sha512_salt_prefix) - 1)
