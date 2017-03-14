--- eventlet/support/greendns.py.orig	2017-02-09 19:38:17 UTC
+++ eventlet/support/greendns.py
@@ -74,7 +74,7 @@ DNS_QUERY_TIMEOUT = 10.0
 HOSTS_TTL = 10.0
 
 EAI_EAGAIN_ERROR = socket.gaierror(socket.EAI_AGAIN, 'Lookup timed out')
-EAI_NODATA_ERROR = socket.gaierror(socket.EAI_NODATA, 'No address associated with hostname')
+EAI_NODATA_ERROR = socket.gaierror(socket.EAI_NONAME, 'No address associated with hostname')
 EAI_NONAME_ERROR = socket.gaierror(socket.EAI_NONAME, 'Name or service not known')
 
 
