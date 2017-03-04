--- deps/v8/src/base/atomicops_internals_arm_gcc.h.orig	2016-10-19 22:02:03 UTC
+++ deps/v8/src/base/atomicops_internals_arm_gcc.h
@@ -13,6 +13,11 @@
 #include <sys/cpuinline.h>
 #endif
 
+#if defined(__FreeBSD__)
+#include <sys/types.h>
+#include <machine/sysarch.h>
+#endif
+
 namespace v8 {
 namespace base {
 
@@ -48,6 +53,8 @@ inline void MemoryBarrier() {
   // Note: This is a function call, which is also an implicit compiler barrier.
   typedef void (*KernelMemoryBarrierFunc)();
   ((KernelMemoryBarrierFunc)0xffff0fa0)();
+#elif defined(__FreeBSD__)
+  sysarch(ARM_DRAIN_WRITEBUF, (void *)0);
 #elif defined(__QNXNTO__)
   __cpu_membarrier();
 #else
@@ -64,8 +71,9 @@ inline void MemoryBarrier() {
     defined(__ARM_ARCH_7__) || defined(__ARM_ARCH_7A__) ||  \
     defined(__ARM_ARCH_7R__) || defined(__ARM_ARCH_7M__) || \
     defined(__ARM_ARCH_6__) || defined(__ARM_ARCH_6J__) ||  \
-    defined(__ARM_ARCH_6K__) || defined(__ARM_ARCH_6Z__) || \
-    defined(__ARM_ARCH_6ZK__) || defined(__ARM_ARCH_6T2__)
+    defined(__ARM_ARCH_6K__) || defined(__ARM_ARCH_6KZ__) || \
+    defined(__ARM_ARCH_6Z__) || defined(__ARM_ARCH_6ZK__) || \
+    defined(__ARM_ARCH_6T2__)
 
 inline Atomic32 NoBarrier_CompareAndSwap(volatile Atomic32* ptr,
                                          Atomic32 old_value,
