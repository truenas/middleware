--- deps/v8/src/base/platform/platform-freebsd.cc.orig	2016-10-19 22:02:03 UTC
+++ deps/v8/src/base/platform/platform-freebsd.cc
@@ -35,6 +35,48 @@
 namespace v8 {
 namespace base {
 
+#ifdef __arm__
+
+bool OS::ArmUsingHardFloat() {
+  // GCC versions 4.6 and above define __ARM_PCS or __ARM_PCS_VFP to specify
+  // the Floating Point ABI used (PCS stands for Procedure Call Standard).
+  // We use these as well as a couple of other defines to statically determine
+  // what FP ABI used.
+  // GCC versions 4.4 and below don't support hard-fp.
+  // GCC versions 4.5 may support hard-fp without defining __ARM_PCS or
+  // __ARM_PCS_VFP.
+
+#define GCC_VERSION (__GNUC__ * 10000                                          \
+                     + __GNUC_MINOR__ * 100                                    \
+                     + __GNUC_PATCHLEVEL__)
+#if GCC_VERSION >= 40600
+#if defined(__ARM_PCS_VFP)
+  return true;
+#else
+  return false;
+#endif
+
+#elif GCC_VERSION < 40500
+  return false;
+
+#else
+#if defined(__ARM_PCS_VFP)
+  return true;
+#elif defined(__ARM_PCS) || defined(__SOFTFP__) || defined(__SOFTFP) || \
+      !defined(__VFP_FP__)
+  return false;
+#else
+#error "Your version of GCC does not report the FP ABI compiled for."          \
+       "Please report it on this issue"                                        \
+       "http://code.google.com/p/v8/issues/detail?id=2140"
+
+#endif
+#endif
+#undef GCC_VERSION
+}
+
+#endif  // def __arm__
+
 
 const char* OS::LocalTimezone(double time, TimezoneCache* cache) {
   if (std::isnan(time)) return "";
