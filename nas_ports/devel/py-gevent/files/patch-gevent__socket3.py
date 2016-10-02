--- gevent/_socket3.py.orig
+++ gevent/_socket3.py
@@ -295,6 +295,15 @@ class socket(object):
                     raise
             self._wait(self._read_event)
 
+    def recvmsg(self, *args):
+        while True:
+            try:
+                return _socket.socket.recvmsg(self._sock, *args)
+            except error as ex:
+                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
+                    raise
+            self._wait(self._read_event)
+
     def recvfrom(self, *args):
         while True:
             try:
@@ -371,6 +380,20 @@ class socket(object):
                     return 0
                 raise
 
+    def sendmsg(self, *args):
+        try:
+            return _socket.socket.sendmsg(self._sock, *args)
+        except error as ex:
+            if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
+                raise
+            self._wait(self._write_event)
+            try:
+                return _socket.socket.sendmsg(self._sock, *args)
+            except error as ex2:
+                if ex2.args[0] == EWOULDBLOCK:
+                    return 0
+                raise
+
     def setblocking(self, flag):
         if flag:
             self.timeout = None
