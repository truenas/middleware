--- src/dns.c.orig	2015-03-10 14:14:45 UTC
+++ src/dns.c
@@ -224,6 +224,15 @@ static int dns_run_pcap_loop (void)
 		pthread_sigmask (SIG_SETMASK, &sigmask, NULL);
 	}
 
+	/* Check for pcap_device, if needed */
+#ifdef __sparc64__
+	if (pcap_device == NULL)
+	{
+		ERROR ("dns plugin: Interface required");
+		return (NULL);
+	}
+#endif
+
 	/* Passing `pcap_device == NULL' is okay and the same as passign "any" */
 	DEBUG ("dns plugin: Creating PCAP object..");
 	pcap_obj = pcap_open_live ((pcap_device != NULL) ? pcap_device : "any",
