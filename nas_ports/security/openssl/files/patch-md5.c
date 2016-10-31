--- crypto/md5/md5.c.orig	2015-01-22 15:58:32.000000000 +0100
+++ crypto/md5/md5.c	2015-03-10 07:02:19.000000000 +0100
@@ -83,7 +83,7 @@
                 err++;
                 continue;
             }
-            printf("MD5(%s)= ", argv[i]);
+            printf("MD5 (%s) = ", argv[i]);
             do_fp(IN);
             fclose(IN);
         }
