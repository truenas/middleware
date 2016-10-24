--- agent/mibgroup/hardware/memory/memory_freebsd.c.orig	2015-02-20 14:44:47 UTC
+++ agent/mibgroup/hardware/memory/memory_freebsd.c
@@ -163,7 +163,7 @@ int netsnmp_mem_arch_load( netsnmp_cache
         if (!mem->descr)
              mem->descr = strdup("Cached memory");
         mem->units = pagesize;
-        mem->size  = cache_count;
+        mem->size  = cache_count + inact_count;
         mem->free  = 0;
     }
 
