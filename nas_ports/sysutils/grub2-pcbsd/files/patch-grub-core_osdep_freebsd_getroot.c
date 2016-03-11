--- grub-core/osdep/freebsd/getroot.c.orig	2015-01-23 02:27:45 UTC
+++ grub-core/osdep/freebsd/getroot.c
@@ -296,6 +296,105 @@ grub_util_get_grub_dev_os (const char *o
   return grub_dev;
 }
 
+int grub_util_check_geom_label(const char *name)
+{
+  struct gmesh mesh;
+  struct gclass *class;
+  struct ggeom *geom;
+  struct gprovider *pp;
+  struct gprovider *pplabel;
+  struct gconsumer *cp;
+  const char *geom_name;
+  const char *test_name;
+  int err;
+
+  err = geom_gettree (&mesh);
+  if (err != 0)
+    grub_util_error ("%s", _("couldn't open geom"));
+
+  LIST_FOREACH (class, &mesh.lg_class, lg_class)
+    if (strcasecmp (class->lg_name, "label") == 0)
+      break;
+  if (!class)
+    grub_util_error ("%s", _("couldn't find geom `label' class"));
+
+  if (strncmp (name, "/dev/", sizeof ("/dev/") - 1) == 0)
+    test_name = name + sizeof ("/dev/") - 1;
+  else
+    test_name = name;
+
+  LIST_FOREACH (geom, &class->lg_geom, lg_geom)
+    {
+     LIST_FOREACH(pp, &geom->lg_provider, lg_provider)
+       {
+         geom_name = pp->lg_name;
+         if (strcasecmp (geom_name, test_name) != 0)
+           continue;
+
+         LIST_FOREACH(cp, &geom->lg_consumer, lg_consumer)
+           {
+             pplabel = cp->lg_provider;
+             if (pplabel == NULL)
+               continue;
+	     return 1;
+           }
+        }
+    }
+  return 0;
+}
+
+const char *
+grub_util_convert_geom_label_to_dev (const char *name, int *full_path)
+{
+  struct gmesh mesh;
+  struct gclass *class;
+  struct ggeom *geom;
+  struct gprovider *pp;
+  struct gprovider *pplabel;
+  struct gconsumer *cp;
+  static char buf[256];
+  const char *geom_name;
+  int err;
+
+  grub_util_info ("Converting label '%s' to device", name);
+
+  err = geom_gettree (&mesh);
+  if (err != 0)
+    grub_util_error ("%s", _("couldn't open geom"));
+
+  LIST_FOREACH (class, &mesh.lg_class, lg_class)
+    if (strcasecmp (class->lg_name, "label") == 0)
+      break;
+  if (!class)
+    grub_util_error ("%s", _("couldn't find geom `label' class"));
+
+
+  LIST_FOREACH (geom, &class->lg_geom, lg_geom)
+    {
+     LIST_FOREACH(pp, &geom->lg_provider, lg_provider)
+       {
+         geom_name = pp->lg_name;
+         if (strcasecmp (geom_name, name) != 0)
+           continue;
+
+         LIST_FOREACH(cp, &geom->lg_consumer, lg_consumer)
+           {
+             pplabel = cp->lg_provider;
+             if (pplabel == NULL)
+               continue;
+
+             if ( full_path )
+               snprintf(buf, sizeof(buf), "/dev/%s", pplabel->lg_name);
+             else
+               snprintf(buf, sizeof(buf), "%s", pplabel->lg_name);
+	     return buf;
+           }
+        }
+    }
+  grub_util_error ("%s", _("couldn't convert gptid to real device name"));
+  return 0;
+}
+
 /* FIXME: geom actually gives us the whole container hierarchy.
    It can be used more efficiently than this.  */
 void
