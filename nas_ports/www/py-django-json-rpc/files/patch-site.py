--- ./jsonrpc/site.py	2012-02-01 23:55:13.000000000 -0800
+++ ./jsonrpc/site.py	2014-01-01 18:30:42.956263864 -0800
@@ -210,7 +210,7 @@
         raise RequestPostError
       else:
         try:
-          D = loads(request.raw_post_data)
+          D = loads(request.body)
         except:
           raise InvalidRequestError
