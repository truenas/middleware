--- grub-core/osdep/unix/platform.c.orig	2014-10-21 10:55:38.203922144 -0400
+++ grub-core/osdep/unix/platform.c	2014-10-21 10:56:54.300915974 -0400
@@ -81,52 +81,8 @@
 static void
 grub_install_remove_efi_entries_by_distributor (const char *efi_distributor)
 {
-  int fd;
-  pid_t pid = grub_util_exec_pipe ((const char * []){ "efibootmgr", NULL }, &fd);
-  char *line = NULL;
-  size_t len = 0;
-
-  if (!pid)
-    {
-      grub_util_warn (_("Unable to open stream from %s: %s"),
-		      "efibootmgr", strerror (errno));
-      return;
-    }
-
-  FILE *fp = fdopen (fd, "r");
-  if (!fp)
-    {
-      grub_util_warn (_("Unable to open stream from %s: %s"),
-		      "efibootmgr", strerror (errno));
-      return;
-    }
-
-  line = xmalloc (80);
-  len = 80;
-  while (1)
-    {
-      int ret;
-      char *bootnum;
-      ret = getline (&line, &len, fp);
-      if (ret == -1)
-	break;
-      if (grub_memcmp (line, "Boot", sizeof ("Boot") - 1) != 0
-	  || line[sizeof ("Boot") - 1] < '0'
-	  || line[sizeof ("Boot") - 1] > '9')
-	continue;
-      if (!strcasestr (line, efi_distributor))
-	continue;
-      bootnum = line + sizeof ("Boot") - 1;
-      bootnum[4] = '\0';
-      if (!verbosity)
-	grub_util_exec ((const char * []){ "efibootmgr", "-q",
-	      "-b", bootnum,  "-B", NULL });
-      else
-	grub_util_exec ((const char * []){ "efibootmgr",
-	      "-b", bootnum, "-B", NULL });
-    }
-
-  free (line);
+  // We don't have efibootmgr on FreeBSD, have to set externally
+  return;
 }
 
 void
@@ -134,40 +90,8 @@
 			   const char *efifile_path,
 			   const char *efi_distributor)
 {
-  const char * efidir_disk;
-  int efidir_part;
-  efidir_disk = grub_util_biosdisk_get_osdev (efidir_grub_dev->disk);
-  efidir_part = efidir_grub_dev->disk->partition ? efidir_grub_dev->disk->partition->number + 1 : 1;
-
-  if (grub_util_exec_redirect_null ((const char * []){ "efibootmgr", "--version", NULL }))
-    {
-      /* TRANSLATORS: This message is shown when required executable `%s'
-	 isn't found.  */
-      grub_util_error (_("%s: not found"), "efibootmgr");
-    }
-
-  /* On Linux, we need the efivars kernel modules.  */
-#ifdef __linux__
-  grub_util_exec ((const char * []){ "modprobe", "-q", "efivars", NULL });
-#endif
-  /* Delete old entries from the same distributor.  */
-  grub_install_remove_efi_entries_by_distributor (efi_distributor);
-
-  char *efidir_part_str = xasprintf ("%d", efidir_part);
-
-  if (!verbosity)
-    grub_util_exec ((const char * []){ "efibootmgr", "-q",
-	  "-c", "-d", efidir_disk,
-	  "-p", efidir_part_str, "-w",
-	  "-L", efi_distributor, "-l", 
-	  efifile_path, NULL });
-  else
-    grub_util_exec ((const char * []){ "efibootmgr",
-	  "-c", "-d", efidir_disk,
-	  "-p", efidir_part_str, "-w",
-	  "-L", efi_distributor, "-l", 
-	  efifile_path, NULL });
-  free (efidir_part_str);
+  // We don't have efibootmgr on FreeBSD, have to set externally
+  return;
 }
 
 void
