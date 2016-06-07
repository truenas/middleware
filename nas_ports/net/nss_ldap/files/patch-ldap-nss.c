--- ldap-nss.c.orig
+++ ldap-nss.c
@@ -69,7 +69,7 @@
 #endif
 
 /* Try to handle systems with both SASL libraries installed */
-#if defined(HAVE_SASL_SASL_H) && defined(HAVE_SASL_AUXPROP_REQUEST)
+#if defined(HAVE_SASL_SASL_H) 
 #include <sasl/sasl.h>
 #elif defined(HAVE_SASL_H)
 #include <sasl.h>
@@ -78,11 +78,11 @@
 #ifndef HAVE_SNPRINTF
 #include "snprintf.h"
 #endif
-#ifdef HAVE_GSSAPI_H
-#include <gssapi.h>
-#elif defined(HAVE_GSSAPI_GSSAPI_KRB5_H)
+#ifdef HAVE_GSSAPI_GSSAPI_KRB5_H
 #include <gssapi/gssapi.h>
 #include <gssapi/gssapi_krb5.h>
+#elif defined(HAVE_GSSAPI_H)
+#include <gssapi.h>
 #endif
 #ifdef CONFIGURE_KRB5_CCNAME
 #include <krb5.h>
