--- helper/mlock/mlock_unavail.go.orig	2016-03-16 19:48:36 UTC
+++ helper/mlock/mlock_unavail.go
@@ -1,4 +1,4 @@
-// +build windows plan9 darwin freebsd openbsd netbsd
+// +build android nacl plan9 windows
 
 package mlock
 
