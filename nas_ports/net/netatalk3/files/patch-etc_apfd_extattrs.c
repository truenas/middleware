--- etc/afpd/extattrs.c.orig	2016-05-18 20:13:19.000000000 -0700
+++ etc/afpd/extattrs.c	2016-05-18 20:16:59.000000000 -0700
@@ -87,6 +87,7 @@
 
     static int          buf_valid = 0;
     static size_t       attrbuflen = 0;
+    bool                close_ad = false;
 
     *rbuflen = 0;
     ibuf += 2;
@@ -176,6 +177,7 @@
                 return AFPERR_MISC;
             }
         } else {
+            close_ad = true;
             FinderInfo = ad_entry(adp, ADEID_FINDERI);
             /* Check if FinderInfo equals default and empty FinderInfo*/
             if (memcmp(FinderInfo, emptyFinderInfo, 32) != 0) {
@@ -238,7 +240,7 @@
     if (ret != AFP_OK)
         buf_valid = 0;
 
-    if (adp)
+    if (close_ad)
         ad_close(adp, ADFLAGS_HF);
 
     return ret;
