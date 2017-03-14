# Description: Fix _ctypes abort on import for FreeBSD/ARM. This is an issue
# for anything !apple that is using the libcompiler_rt provided by clang on arm
# PR: ports/149167 ports/184517
# Patch by: cognet@ (to be upstreamed @ LLVM)

--- ./Modules/_ctypes/libffi/src/arm/ffi.c.orig	2013-11-17 18:22:57.000000000 +1100
+++ ./Modules/_ctypes/libffi/src/arm/ffi.c	2013-12-03 19:23:24.521993369 +1100
@@ -33,6 +33,11 @@
 
 #include <stdlib.h>
 
+#if defined(__FreeBSD__) && defined(__arm__)
+#include <sys/types.h>
+#include <machine/sysarch.h>
+#endif
+
 /* Forward declares. */
 static int vfp_type_p (ffi_type *);
 static void layout_vfp_args (ffi_cif *);
@@ -582,6 +587,16 @@
 
 #else
 
+#if defined(__FreeBSD__) && defined(__arm__)
+#define __clear_cache(start, end) do { \
+		struct arm_sync_icache_args ua; 		\
+								\
+		ua.addr = (uintptr_t)(start);			\
+		ua.len = (char *)(end) - (char *)start;		\
+		sysarch(ARM_SYNC_ICACHE, &ua);			\
+	} while (0);
+#endif
+
 #define FFI_INIT_TRAMPOLINE(TRAMP,FUN,CTX)				\
 ({ unsigned char *__tramp = (unsigned char*)(TRAMP);			\
    unsigned int  __fun = (unsigned int)(FUN);				\
