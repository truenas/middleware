--- ./lib/include/vm_basic_types.h.orig	2010-10-20 05:19:54.000000000 +0900
+++ ./lib/include/vm_basic_types.h	2010-10-29 20:11:03.000000000 +0900
@@ -333,6 +333,7 @@
          #define FMTPD  ""
       #endif
    #elif defined(__linux__) \
+      || (defined(__clang__)) \
       || (defined(_POSIX_C_SOURCE) && _POSIX_C_SOURCE >= 200112L) \
       || (defined(_POSIX_VERSION) && _POSIX_VERSION >= 200112L) \
       || (defined(_POSIX2_VERSION) && _POSIX2_VERSION >= 200112L)
