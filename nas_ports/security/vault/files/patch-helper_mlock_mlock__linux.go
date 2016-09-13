--- helper/mlock/mlock_linux.go.orig	2016-03-16 19:48:36 UTC
+++ helper/mlock/mlock_linux.go
@@ -1,14 +0,0 @@
-// +build linux
-
-package mlock
-
-import "syscall"
-
-func init() {
-	supported = true
-}
-
-func lockMemory() error {
-	// Mlockall prevents all current and future pages from being swapped out.
-	return syscall.Mlockall(syscall.MCL_CURRENT | syscall.MCL_FUTURE)
-}
