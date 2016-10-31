--- ssl/srtp.h.orig	2015-03-19 14:30:36.000000000 +0100
+++ ssl/srtp.h	2015-03-19 21:12:51.000000000 +0100
@@ -136,7 +136,6 @@
 int SSL_set_tlsext_use_srtp(SSL *ctx, const char *profiles);
 
 STACK_OF(SRTP_PROTECTION_PROFILE) *SSL_get_srtp_profiles(SSL *ssl);
-SRTP_PROTECTION_PROFILE *SSL_get_selected_srtp_profile(SSL *s);
 
 # endif
 
