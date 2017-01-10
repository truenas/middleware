--- lib/include/vm_basic_asm.h.orig	2013-11-13 03:22:29.000000000 +0000
+++ lib/include/vm_basic_asm.h	2013-11-13 03:24:26.000000000 +0000
@@ -208,7 +208,7 @@
 GetCallerEFlags(void)
 {
    unsigned long flags;
-   asm volatile("pushf; pop %0" : "=r"(flags));
+   __asm__ volatile("pushf; pop %0" : "=r"(flags));
    return flags;
 }
 
