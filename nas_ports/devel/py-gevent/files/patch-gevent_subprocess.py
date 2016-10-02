--- gevent/subprocess.py.orig	2016-02-16 14:04:11.213929650 -0800
+++ gevent/subprocess.py	2016-02-16 14:04:27.153929455 -0800
@@ -138,6 +138,32 @@
 __all__ = __implements__ + __imports__
 
 
+# This routine below is a pure python
+# translation of python's _posixsubprocess.c's
+# _is_fdescfs_mounted_on_dev_fd method
+# https://hg.python.org/cpython/file/3f3cbfd52f94/Modules/_posixsubprocess.c
+def bsd_is_devfs_mounted():
+    """
+    Checks if fdescfs is truly mounted on /dev/fd
+    Returns True if yes else False
+    """
+    dev_stdev = os.stat('/dev').st_dev
+    dev_fd_stdev = os.stat('/dev/fd').st_dev
+    if (dev_stdev == 0 or dev_fd_stdev == 0 or dev_stdev == dev_fd_stdev):
+        # This means that the either the /dev/fd is only there for purely
+        # devfs reasons or something else is funky thus return False
+        return False
+    return True
+
+# devfs path string template
+devfs_path_template = None
+if sys.platform.startswith('freebsd'):
+    if bsd_is_devfs_mounted():
+        devfs_path_template = '/dev/fd'
+elif sys.platform.startswith('linux'):
+    devfs_path_template = '/proc/{0}/fd'
+
+
 mswindows = sys.platform == 'win32'
 if mswindows:
     import msvcrt
@@ -913,6 +939,11 @@
             self._set_cloexec_flag(w)
             return r, w
 
+        def _get_max_fd(self):
+            if devfs_path_template is None:
+                return MAXFD
+            return int(max(os.listdir(devfs_path_template.format(self.pid))))
+
         def _close_fds(self, keep):
             # `keep` is a set of fds, so we
             # use os.closerange from 3 to min(keep)
@@ -929,7 +960,7 @@
                 min_keep = min(keep)
                 max_keep = max(keep)
                 os.closerange(3, min_keep)
-                os.closerange(max_keep + 1, MAXFD)
+                os.closerange(max_keep + 1, self._get_max_fd())
                 for i in xrange(min_keep, max_keep):
                     if i in keep:
                         set_inheritable(i, True)
@@ -940,7 +971,7 @@
                     except:
                         pass
             else:
-                for i in xrange(3, MAXFD):
+                for i in xrange(3, self._get_max_fd()):
                     if i in keep:
                         set_inheritable(i, True)
                         continue
@@ -1059,7 +1090,7 @@
                                 # are closed, and inheritable handles
                                 # are only inherited if the close_fds
                                 # parameter is False."
-                                for i in xrange(3, MAXFD):
+                                for i in xrange(3, self._get_max_fd()):
                                     try:
                                         if i == errpipe_write or os.get_inheritable(i):
                                             continue
