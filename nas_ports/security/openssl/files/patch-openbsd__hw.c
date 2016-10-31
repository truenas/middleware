--- crypto/evp/openbsd_hw.c.orig	2015-01-22 15:58:32.000000000 +0100
+++ crypto/evp/openbsd_hw.c	2015-03-10 07:08:45.000000000 +0100
@@ -108,7 +108,10 @@
             dev_failed = 1;
             return 0;
         }
-        close(cryptodev_fd);
+        if (fd == -1)
+            fd = cryptodev_fd;
+        else
+            close(cryptodev_fd);
     }
     assert(ses);
     memset(ses, '\0', sizeof *ses);
