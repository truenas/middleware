--- src/gevent/subprocess.py.orig	2017-02-14 20:18:49 UTC
+++ src/gevent/subprocess.py
@@ -702,10 +702,12 @@ class Popen(object):
         self._stdout_buffer = None
         stderr_value = self._stderr_buffer
         self._stderr_buffer = None
-        # XXX: Under python 3 in universal newlines mode we should be
-        # returning str, not bytes
-        return (None if stdout is None else stdout_value or b'',
-                None if stderr is None else stderr_value or b'')
+        if PY3 and (self.encoding or self.errors or self.universal_newlines):
+            empty_value = ''
+        else:
+            empty_value = b''
+        return (None if stdout is None else stdout_value or empty_value,
+                None if stderr is None else stderr_value or empty_value)
 
     def poll(self):
         """Check if child process has terminated. Set and return :attr:`returncode` attribute."""
