--- agent/mibgroup/udp-mib/data_access/udp_endpoint_freebsd4.c.orig	2015-10-13 12:04:44 UTC
+++ agent/mibgroup/udp-mib/data_access/udp_endpoint_freebsd4.c
@@ -187,6 +187,8 @@ _load(netsnmp_container *container, u_in
         CONTAINER_INSERT(container, entry);
     }
 
+    free(udpcb_buf);
+
     if(rc<0)
         return rc;
 
