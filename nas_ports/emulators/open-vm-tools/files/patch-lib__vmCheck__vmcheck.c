--- ./lib/vmCheck/vmcheck.c.orig	2013-09-23 15:51:10.000000000 +0000
+++ ./lib/vmCheck/vmcheck.c	2014-04-23 15:36:44.323843725 +0000
@@ -134,6 +134,7 @@
 #else
    do {
       int signals[] = {
+         SIGBUS,
          SIGILL,
          SIGSEGV,
       };
