--- helper/mlock/mlock_solaris.go.orig	2016-03-16 19:48:36 UTC
+++ helper/mlock/mlock_solaris.go
@@ -1,17 +0,0 @@
-// +build solaris
-
-package mlock
-
-import (
-       "syscall"
-       "golang.org/x/sys/unix"
-)
-
-func init() {
-       supported = true
-}
-
-func lockMemory() error {
-       // Mlockall prevents all current and future pages from being swapped out.
-       return unix.Mlockall(syscall.MCL_CURRENT | syscall.MCL_FUTURE)
-}
