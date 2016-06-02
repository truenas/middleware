--- grub-core/loader/i386/bsd.c.orig	2015-01-30 16:34:55 UTC
+++ grub-core/loader/i386/bsd.c
@@ -42,12 +42,14 @@
 GRUB_MOD_LICENSE ("GPLv3+");
 
 #include <grub/video.h>
+#include <grub/acpi.h>
 #ifdef GRUB_MACHINE_PCBIOS
 #include <grub/machine/biosnum.h>
 #endif
 #ifdef GRUB_MACHINE_EFI
 #include <grub/efi/efi.h>
 #define NETBSD_DEFAULT_VIDEO_MODE "800x600"
+#define FREEBSD_DEFAULT_VIDEO_MODE "auto"
 #else
 #define NETBSD_DEFAULT_VIDEO_MODE "text"
 #include <grub/i386/pc/vbe.h>
@@ -585,6 +587,72 @@ freebsd_get_zfs (void)
   grub_free (uuid);
 }
 
+#ifdef GRUB_MACHINE_EFI
+
+static grub_err_t
+grub_freebsd_setup_video (void)
+{
+  struct grub_video_mode_info mode_info;
+  void *framebuffer;
+  const char *modevar;
+  struct grub_freebsd_btinfo_framebuf efifb;
+  grub_err_t err;
+  grub_video_driver_id_t driv_id;
+
+  modevar = grub_env_get ("gfxpayload");
+
+  /* Now all graphical modes are acceptable.
+     May change in future if we have modes without framebuffer.  */
+  if (modevar && *modevar != 0)
+    {
+      char *tmp;
+      tmp = grub_xasprintf ("%s;" FREEBSD_DEFAULT_VIDEO_MODE, modevar);
+      if (! tmp)
+	return grub_errno;
+      err = grub_video_set_mode (tmp, 0, 0);
+      grub_free (tmp);
+    }
+  else
+    err = grub_video_set_mode (FREEBSD_DEFAULT_VIDEO_MODE, 0, 0);
+
+  if (err)
+    return err;
+
+  driv_id = grub_video_get_driver_id ();
+  if (driv_id == GRUB_VIDEO_DRIVER_NONE)
+    return GRUB_ERR_NONE;
+
+  err = grub_video_get_info_and_fini (&mode_info, &framebuffer);
+
+  if (err)
+    return err;
+
+  efifb.fb_width = mode_info.width;
+  efifb.fb_height = mode_info.height;
+  efifb.fb_stride = mode_info.pitch / mode_info.bytes_per_pixel;
+
+  efifb.fb_addr = (grub_addr_t) framebuffer;
+  efifb.fb_size = ALIGN_UP (mode_info.pitch * efifb.fb_height, 65536);
+
+  if ( mode_info.blue_field_pos == 16 ) {
+    efifb.fb_mask_red = 0x000000ff;
+    efifb.fb_mask_green = 0x0000ff00;
+    efifb.fb_mask_blue = 0x00ff0000;
+  }
+
+  if ( mode_info.blue_field_pos == 0 ) {
+    efifb.fb_mask_red = 0x00ff0000;
+    efifb.fb_mask_green = 0x0000ff00;
+    efifb.fb_mask_blue = 0x000000ff;
+  }
+
+  efifb.fb_mask_reserved = 0xff000000;
+
+  err = grub_bsd_add_meta ( FREEBSD_MODINFO_METADATA | FREEBSD_BTINFO_FRAMEBUF, &efifb, sizeof (efifb));
+  return err;
+}
+#endif
+
 static grub_err_t
 grub_freebsd_boot (void)
 {
@@ -603,6 +671,55 @@ grub_freebsd_boot (void)
 
   bi.boot_device = freebsd_biosdev;
 
+#ifdef GRUB_MACHINE_EFI
+  /* When booting in EFI mode, we need to export some additional kernel ACPI hints */
+  struct grub_acpi_rsdp_v10 *v1;
+  struct grub_acpi_rsdp_v20 *v2;
+  v1 = grub_acpi_get_rsdpv1 ();
+  v2 = grub_acpi_get_rsdpv2 ();
+  if (v2 && v2->length > 40)
+    v2 = 0;
+
+  int revision;
+  char acpiBuf[24];
+
+  if (v1)
+  {
+     revision = v1->revision;
+     if ( revision == 0 )
+        revision = 1;
+     grub_snprintf (acpiBuf, sizeof (acpiBuf), "%d", revision);
+     grub_env_set("kFreeBSD.hint.acpi.0.revision", acpiBuf);
+
+     grub_snprintf (acpiBuf, sizeof (acpiBuf), "%s", v1->oemid);
+     grub_env_set("kFreeBSD.hint.acpi.0.oem", acpiBuf);
+
+     grub_snprintf (acpiBuf, sizeof (acpiBuf), "0x%016x", v1->rsdt_addr);
+     grub_env_set("kFreeBSD.hint.acpi.0.rsdt", acpiBuf);
+
+     grub_snprintf (acpiBuf, sizeof (acpiBuf), "0x%016llx", (unsigned long long)v1);
+     grub_env_set("kFreeBSD.hint.acpi.0.rsdp", acpiBuf);
+  }
+
+  if (v2)
+  {
+     revision = v2->rsdpv1.revision;
+     if ( revision == 0 )
+        revision = 1;
+
+     grub_snprintf (acpiBuf, sizeof (acpiBuf), "%d", revision);
+     grub_env_set("kFreeBSD.hint.acpi.0.revision", acpiBuf);
+
+     grub_snprintf (acpiBuf, sizeof (acpiBuf), "0x%016llx", (unsigned long long)v2->xsdt_addr);
+     grub_env_set("kFreeBSD.hint.acpi.0.xsdt", acpiBuf);
+
+     grub_snprintf (acpiBuf, sizeof (acpiBuf), "%d", v2->length);
+     grub_env_set("kFreeBSD.hint.acpi.0.xsdt_length", acpiBuf);
+  }
+
+
+#endif
+
   p_size = 0;
   FOR_SORTED_ENV (var)
     if ((grub_memcmp (var->name, "kFreeBSD.", sizeof("kFreeBSD.") - 1) == 0) && (var->name[sizeof("kFreeBSD.") - 1]))
@@ -688,6 +805,10 @@ grub_freebsd_boot (void)
 		*(grub_uint32_t *) p_tag = bootflags;
 	      break;
 
+	    case FREEBSD_MODINFO_METADATA | FREEBSD_BTINFO_FRAMEBUF:
+	      grub_memcpy (p_tag, tag->data, tag->len);
+	      break;
+
 	    case FREEBSD_MODINFO_METADATA | FREEBSD_MODINFOMD_ENVP:
 	      if (is_64bit)
 		*(grub_uint64_t *) p_tag = bi.environment;
@@ -717,7 +838,10 @@ grub_freebsd_boot (void)
 
   bi.kern_end = kern_end;
 
+#ifndef GRUB_MACHINE_EFI
+  /* Don't set text mode on EFI boot */
   grub_video_set_mode ("text", 0, 0);
+#endif
 
   if (is_64bit)
     {
@@ -1561,6 +1685,16 @@ grub_cmd_freebsd (grub_extcmd_context_t 
 				   FREEBSD_MODINFOMD_KERNEND, &data, len);
 	  if (err)
 	    return err;
+
+#ifdef GRUB_MACHINE_EFI
+	  err = grub_freebsd_setup_video ();
+	  if (err)
+	  {
+	    grub_print_error ();
+	    grub_puts_ (N_("Booting in EFI blind mode"));
+	    grub_errno = GRUB_ERR_NONE;
+	  }
+#endif
 	}
       grub_bsd_get_device (&freebsd_biosdev, &unit, &slice, &part);
       freebsd_zfsguid = 0;
