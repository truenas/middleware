--- snmplib/snmpusm.c.orig	2011-07-27 09:58:24.000000000 -0300
+++ snmplib/snmpusm.c	2011-07-27 09:57:48.000000000 -0300
@@ -91,6 +91,8 @@
 oid             usmAESPrivProtocol[10] = { 1, 3, 6, 1, 6, 3, 10, 1, 2, 4 };
 /* backwards compat */
 oid             *usmAES128PrivProtocol = usmAESPrivProtocol;
+oid             *usmAES192PrivProtocol = usmAESPrivProtocol;
+oid             *usmAES256PrivProtocol = usmAESPrivProtocol;
 
 static u_int    dummy_etime, dummy_eboot;       /* For ISENGINEKNOWN(). */
 
