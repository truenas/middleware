--- helper/mlock/mlock_unix.go.orig	2016-04-11 17:33:59 UTC
+++ helper/mlock/mlock_unix.go
@@ -0,0 +1,18 @@
+// +build darwin dragonfly freebsd linux netbsd openbsd solaris
+
+package mlock
+
+import (
+	"syscall"
+
+	"golang.org/x/sys/unix"
+)
+
+func init() {
+	supported = true
+}
+
+func lockMemory() error {
+	// Mlockall prevents all current and future pages from being swapped out.
+	return unix.Mlockall(syscall.MCL_CURRENT | syscall.MCL_FUTURE)
+}
