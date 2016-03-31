--- clientserver.c.orig	2015-08-19 02:17:59.728349387 -0700
+++ clientserver.c	2015-08-19 02:17:59.718154675 -0700
@@ -501,6 +501,39 @@
 }
 #endif
 
+// Stupid function to perform trim on string (i.e. eat whitespaces)
+char *trim(char *str)
+{
+	size_t len = 0;
+	char *frontp = str;
+	char *endp = NULL;
+
+	if (str == NULL) { return NULL; }
+	if (str[0] == '\0') { return str; }
+
+	len = strlen(str);
+	endp = str + len;
+
+	/* Move the front and back pointers to address the first non-whitespace
+	* characters from each end.
+	*/
+	while (isspace(*frontp)) { ++frontp; }
+	while (endp != frontp && isspace(*(--endp)));
+	*(endp + 1) = '\0';
+
+	/* Shift the string so that it starts at str so that if it's dynamically
+	* allocated, we can still free it on the returned pointer.  Note the reuse
+	* of endp to mean the front of the string buffer now.
+	*/
+	endp = str;
+	if (frontp != str) {
+	while (*frontp) { *endp++ = *frontp++; }
+	*endp = '\0';
+	}
+	return str;
+}
+
+
 static int rsync_module(int f_in, int f_out, int i, const char *addr, const char *host)
 {
 	int argc;
@@ -599,24 +632,49 @@
 	} else
 		set_uid = 0;
 
-	p = *lp_gid(i) ? strtok(lp_gid(i), ", ") : NULL;
+	p = *lp_gid(i) ? lp_gid(i) : NULL;
 	if (p) {
 		/* The "*" gid must be the first item in the list. */
-		if (strcmp(p, "*") == 0) {
+		char *token = NULL;
+		char *temp = NULL;
+		char *from = p;
+		token = strchr(p, ',');
+		if ( token != NULL ) {
+			temp = (char*) malloc(token-from+1);
+			strlcpy(temp, from, token-from+1);
+			from = token+1;
+			token = strchr(from, ',');
+			if (strcmp(trim(temp), "*") == 0) {
 #ifdef HAVE_GETGROUPLIST
-			if (want_all_groups(f_out, uid) < 0)
-				return -1;
+				if (want_all_groups(f_out, uid) < 0)
+					return -1;
 #elif defined HAVE_INITGROUPS
-			if ((pw = want_all_groups(f_out, uid)) == NULL)
-				return -1;
+				if ((pw = want_all_groups(f_out, uid)) == NULL)
+					return -1;
 #else
-			rprintf(FLOG, "This rsync does not support a gid of \"*\"\n");
-			io_printf(f_out, "@ERROR: invalid gid setting.\n");
-			return -1;
+				rprintf(FLOG, "This rsync does not support a gid of \"*\"\n");
+				io_printf(f_out, "@ERROR: invalid gid setting.\n");
+				return -1;
 #endif
-		} else if (add_a_group(f_out, p) < 0)
-			return -1;
-		while ((p = strtok(NULL, ", ")) != NULL) {
+			} else if (add_a_group(f_out, trim(temp)) < 0)
+				return -1;
+			free(temp);
+			while ( token != NULL) {
+#if defined HAVE_INITGROUPS && !defined HAVE_GETGROUPLIST
+				if (pw) {
+					rprintf(FLOG, "This rsync cannot add groups after \"*\".\n");
+					io_printf(f_out, "@ERROR: invalid gid setting.\n");
+					return -1;
+				}
+#endif
+				temp = (char*) malloc(token-from+1);
+				strlcpy(temp, from, p-from+1);
+				if (add_a_group(f_out, trim(temp)) < 0)
+					return -1;
+				from = p+1;
+				token = strchr(from, ',');
+				free(temp);
+			}
 #if defined HAVE_INITGROUPS && !defined HAVE_GETGROUPLIST
 			if (pw) {
 				rprintf(FLOG, "This rsync cannot add groups after \"*\".\n");
@@ -624,7 +682,28 @@
 				return -1;
 			}
 #endif
-			if (add_a_group(f_out, p) < 0)
+			temp = (char*) malloc(strlen(p)+1);
+			strlcpy(temp, from, strlen(p)+1);
+			if (add_a_group(f_out, trim(temp)) < 0)
+				return -1;
+			free(token);
+		}
+		else {
+			temp = (char*) malloc(strlen(p)+1);
+			strlcpy(temp, from, strlen(p)+1);
+			if (strcmp(trim(temp), "*") == 0) {
+#ifdef HAVE_GETGROUPLIST
+				if (want_all_groups(f_out, uid) < 0)
+					return -1;
+#elif defined HAVE_INITGROUPS
+				if ((pw = want_all_groups(f_out, uid)) == NULL)
+					return -1;
+#else
+				rprintf(FLOG, "This rsync does not support a gid of \"*\"\n");
+				io_printf(f_out, "@ERROR: invalid gid setting.\n");
+				return -1;
+#endif
+			} else if (add_a_group(f_out, trim(temp)) < 0)
 				return -1;
 		}
 	} else if (am_root) {
