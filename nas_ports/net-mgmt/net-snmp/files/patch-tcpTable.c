--- agent/mibgroup/mibII/tcpTable.c.orig	2011-07-01 19:35:46.000000000 -0300
+++ agent/mibgroup/mibII/tcpTable.c	2011-07-27 10:00:57.000000000 -0300
@@ -298,8 +298,10 @@
 #ifndef NETSNMP_FEATURE_REMOVE_TCP_COUNT_CONNECTIONS
 int
 TCP_Count_Connections( void ) {
+#if (defined(CAN_USE_SYSCTL) && defined(TCPCTL_PCBLIST))
     tcpTable_load(NULL, NULL);
     return tcp_estab;
+#endif
 }
 #endif /* NETSNMP_FEATURE_REMOVE_TCP_COUNT_CONNECTIONS */
 
