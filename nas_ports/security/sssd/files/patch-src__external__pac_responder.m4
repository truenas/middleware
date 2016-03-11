--- src/external/pac_responder.m4.orig	2014-09-17 15:01:37.000000000 +0200
+++ src/external/pac_responder.m4	2015-11-26 10:14:25.245313290 +0100
@@ -14,14 +14,16 @@
     PKG_CHECK_MODULES(NDR_KRB5PAC, ndr_krb5pac, ndr_krb5pac_ok=yes,
         AC_MSG_WARN([Cannot build pac responder without libndr_krb5pac]))
 
-    AC_PATH_PROG(KRB5_CONFIG, krb5-config)
+    AC_PATH_PROG(KRB5_CONFIG, krb5-config, [], [/usr/local/bin:$PATH])
     AC_MSG_CHECKING(for supported MIT krb5 version)
     KRB5_VERSION="`$KRB5_CONFIG --version`"
     case $KRB5_VERSION in
         Kerberos\ 5\ release\ 1.9* | \
         Kerberos\ 5\ release\ 1.10* | \
         Kerberos\ 5\ release\ 1.11* | \
-        Kerberos\ 5\ release\ 1.12*)
+        Kerberos\ 5\ release\ 1.12* | \
+        Kerberos\ 5\ release\ 1.13* | \
+        Kerberos\ 5\ release\ 1.14*)
             krb5_version_ok=yes
             AC_MSG_RESULT([yes])
             ;;
