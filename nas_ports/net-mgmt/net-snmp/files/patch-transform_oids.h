--- include/net-snmp/library/transform_oids.h.orig	2006-10-28 05:19:44.000000000 +0900
+++ include/net-snmp/library/transform_oids.h	2008-03-26 07:50:45.393507729 +0900
@@ -23,6 +23,8 @@
 /* XXX: OIDs not defined yet */
 NETSNMP_IMPORT oid      usmAESPrivProtocol[10]; /* == { 1,3,6,1,6,3,10,1,2,4 }; */
 NETSNMP_IMPORT oid      *usmAES128PrivProtocol; /* backwards compat */
+NETSNMP_IMPORT oid      *usmAES192PrivProtocol; /* backwards compat */
+NETSNMP_IMPORT oid      *usmAES256PrivProtocol; /* backwards compat */
 
 #define USM_AUTH_PROTO_NOAUTH_LEN 10
 #define USM_AUTH_PROTO_MD5_LEN 10
