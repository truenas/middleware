--- modules/freebsd/vmhgfs/kernelStubs.h.orig	2010-10-20 05:19:54.000000000 +0900
+++ modules/freebsd/vmhgfs/kernelStubs.h	2010-11-16 13:26:24.000000000 +0900
@@ -132,7 +132,7 @@
  * Stub functions we provide.
  */
 
-void Panic(const char *fmt, ...);
+/* void Panic(const char *fmt, ...); -> vm_assert.h */
 
 char *Str_Strcpy(char *buf, const char *src, size_t maxSize);
 int Str_Vsnprintf(char *str, size_t size, const char *format,
