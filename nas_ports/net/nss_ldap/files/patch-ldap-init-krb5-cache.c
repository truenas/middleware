--- ldap-init-krb5-cache.c.orig
+++ ldap-init-krb5-cache.c
@@ -109,14 +109,14 @@
 #include <gssapi/gssapi.h>
 #include <gssapi/gssapi_krb5.h>
 
+#ifndef HOST_NAME_MAX
+#define HOST_NAME_MAX 1024
+#endif
+
 #define MAX_RENEW_TIME "365d"
 
 #define KT_PATH_MAX 256
 
-#ifndef HEIMDAL
-typedef struct _profile_t *profile_t;
-#endif
-
 /* State machine items */
 typedef enum
 {
@@ -213,14 +213,25 @@
 {
   krb5_error_code code = 0;
   krb5_keytab __keytab;
+#ifdef HEIMDAL
+  char kttypebuf[KRB5_KT_PREFIX_MAX_LEN];
+  size_t kttypesize = sizeof kttypebuf;
+#endif
+  char *kttype;
 
   debug ("==> krb5_cache_kt_is_accessible: ktname %s", __ktname);
   assert (context != NULL);
   if (!(code = krb5_kt_resolve (context, __ktname, &__keytab)))
     {
+#ifdef HEIMDAL
+      krb5_kt_get_type (context, __keytab, kttypebuf, kttypesize);
+      kttype = kttypebuf;
+#else
+      kttype = krb5_kt_get_type (context, __keytab);
+#endif
       debug ("==> krb5_cache_kt_is_accessible: resolved ktname %s - %s",
-	     __ktname, krb5_kt_get_type (context, __keytab));
-      if (strcmp ("FILE", krb5_kt_get_type (context, __keytab)) == 0)
+	     __ktname, kttype);
+      if (strcmp ("FILE", kttype) == 0)
 	{
 	  debug ("==> krb5_cache_kt_is_accessible: kt type = FILE");
 	  uid_t ruid = getuid ();
@@ -243,7 +254,7 @@
 	    {
 	      setreuid (ruid, euid);
 	    }
-	  if (rgid != rgid)
+	  if (rgid != egid)
 	    {
 	      setregid (rgid, egid);
 	    }
@@ -542,7 +553,7 @@
     }
   profile_release (profile);
 #else
-  skew = context->max_skew;
+  /* skew = context->max_skew; */
 #endif
   ccname = krb5_cache_get_ccname (config);
   debug ("==> krb5_cache_setup: credential cache name %s",
@@ -671,7 +682,11 @@
 		     ccname ? ccname : "NULL");
 		}
 	    }
+#ifdef HEIMDAL
+	  free (principal_name);
+#else
 	  krb5_free_unparsed_name (context, principal_name);
+#endif
 	}
     }
 
