--- ldap-ethers.h.orig	2009-11-06 10:28:08.000000000 +0000
+++ ldap-ethers.h	2009-12-23 17:02:06.000000000 +0000
@@ -32,7 +32,7 @@
 
 #ifndef HAVE_STRUCT_ETHER_ADDR
 struct ether_addr {
-  u_char ether_addr_octet[6];
+  u_char octet[6];
 };
 #endif
 
