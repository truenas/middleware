diff --git src/util/crypto/libcrypto/crypto_sha512crypt.c src/util/crypto/libcrypto/crypto_sha512crypt.c
index 34547d0..6901851 100644
--- src/util/crypto/libcrypto/crypto_sha512crypt.c
+++ src/util/crypto/libcrypto/crypto_sha512crypt.c
@@ -28,6 +28,12 @@
 #include <openssl/evp.h>
 #include <openssl/rand.h>
 
+void *
+mempcpy (void *dest, const void *src, size_t n)
+{
+  return (char *) memcpy (dest, src, n) + n;
+}
+
 /* Define our magic string to mark salt for SHA512 "encryption" replacement. */
 const char sha512_salt_prefix[] = "$6$";
 #define SALT_PREF_SIZE (sizeof(sha512_salt_prefix) - 1)
