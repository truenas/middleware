--- agent/mibgroup/tcp-mib/data_access/tcpConn_freebsd4.c.orig	2015-10-13 12:04:38 UTC
+++ agent/mibgroup/tcp-mib/data_access/tcpConn_freebsd4.c
@@ -216,6 +216,8 @@ _load(netsnmp_container *container, u_in
         CONTAINER_INSERT(container, entry);
     }
 
+    free(tcpcb_buf);
+
     if(rc<0)
         return rc;
 
