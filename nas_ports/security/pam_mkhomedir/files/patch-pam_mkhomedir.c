--- pam_mkhomedir.c.orig	2016-05-25 08:06:06.324447000 -0500
+++ pam_mkhomedir.c	2016-05-25 08:09:46.686258000 -0500
@@ -211,9 +211,11 @@
 		goto err;
 	}
 
-	copymkdir(pwd->pw_dir, skeldir, getmode(set, S_IRWXU | S_IRWXG | S_IRWXO), pwd->pw_uid,pwd->pw_gid);
-	free(set);
-	return (PAM_SUCCESS);
+	if (strcmp(pwd->pw_dir,"/nonexistent") != 0 ) {
+	        copymkdir(pwd->pw_dir, skeldir, getmode(set, S_IRWXU | S_IRWXG | S_IRWXO), pwd->pw_uid,pwd->pw_gid);
+		free(set);
+		return (PAM_SUCCESS);
+	}
 
 err:
 	if (openpam_get_option(pamh, "no_fail"))
