--- ldap-ethers.c.orig	2009-11-06 10:28:08.000000000 +0000
+++ ldap-ethers.c	2009-12-23 17:01:14.000000000 +0000
@@ -217,9 +217,9 @@
     }
 
   snprintf(fullmac, sizeof(fullmac), "%02x:%02x:%02x:%02x:%02x:%02x",
-	   addr->ether_addr_octet[0], addr->ether_addr_octet[1],
-	   addr->ether_addr_octet[2], addr->ether_addr_octet[3],
-	   addr->ether_addr_octet[4], addr->ether_addr_octet[5]);
+	   addr->octet[0], addr->octet[1],
+	   addr->octet[2], addr->octet[3],
+	   addr->octet[4], addr->octet[5]);
 
   LA_INIT(a);
   LA_STRING(a) = ether_ntoa(addr);
@@ -343,14 +343,14 @@
 	if (i != 6)
 		return NULL;
 	for (i = 0; i < 6; i++)
-		ep.ether_addr_octet[i] = t[i];
+		ep.octet[i] = t[i];
 
 	return &ep;
 }
 #endif /* !HAVE_ETHER_ATON */
 
 #ifndef HAVE_ETHER_NTOA
-#define EI(i)	(unsigned int)(e->ether_addr_octet[(i)])
+#define EI(i)	(unsigned int)(e->octet[(i)])
 static char *ether_ntoa (const struct ether_addr *e)
 {
 	static char s[18];
