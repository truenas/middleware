--- src/cputemp.c.orig	2016-05-22 07:11:11 UTC
+++ src/cputemp.c
@@ -0,0 +1,97 @@
+//+
+// Copyright 2016 iXsystems, Inc.
+// All rights reserved
+//
+// Redistribution and use in source and binary forms, with or without
+// modification, are permitted providing that the following conditions
+// are met:
+// 1. Redistributions of source code must retain the above copyright
+//    notice, this list of conditions and the following disclaimer.
+// 2. Redistributions in binary form must reproduce the above copyright
+//    notice, this list of conditions and the following disclaimer in the
+//    documentation and/or other materials provided with the distribution.
+//
+// THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
+// IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
+// WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
+// ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
+// DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
+// DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
+// OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
+// HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
+// STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
+// IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
+// POSSIBILITY OF SUCH DAMAGE.
+//
+///////////////////////////////////////////////////////////////////////////////
+
+#include "collectd.h"
+#include "plugin.h"
+#include "common.h"
+#include "utils_cache.h"
+
+#include <sys/types.h>
+#include <sys/sysctl.h>
+
+static int numcpu;
+
+static int init (void)
+{
+    size_t numcpu_size;
+
+    numcpu_size = sizeof (numcpu);
+
+    if (sysctlbyname ("hw.ncpu", &numcpu, &numcpu_size, NULL, 0) < 0)
+    {
+        char errbuf[1024];
+        WARNING ("cputemp plugin: sysctlbyname(hw.ncpu): %s",
+                 sstrerror (errno, errbuf, sizeof (errbuf)));
+        return (-1);
+    }
+
+    return 0;
+}
+
+static int temp_read (void)
+{
+    size_t temp_len;
+    int temp, i;
+
+    temp_len = sizeof(temp);
+
+    for (i = 0; i < numcpu; i++) {
+        value_t values[1];
+        value_list_t vl = VALUE_LIST_INIT;
+        char name_buf[50];
+
+        ssnprintf (name_buf, sizeof (name_buf), "dev.cpu.%d.temperature", i);
+
+        if (sysctlbyname(name_buf, &temp, &temp_len, NULL, 0) < 0) {
+            char errbuf[1024];
+            WARNING("cputemp plugin: sysctl(dev.cpu.%d.temperature): %s",
+                    i,
+                    sstrerror(errno, errbuf, sizeof(errbuf)));
+            return (-1);
+        }
+        values[0].gauge = temp;
+
+        vl.values = values;
+        vl.values_len = 1;
+        vl.time = cdtime();
+        sstrncpy (vl.host, hostname_g, sizeof(vl.host));
+        sstrncpy (vl.plugin, "cputemp", sizeof(vl.plugin));
+        sstrncpy (vl.type, "temperature", sizeof(vl.type));
+        ssnprintf (vl.plugin_instance, sizeof (vl.plugin_instance), "%i", i);
+
+        plugin_dispatch_values(&vl);
+    }
+
+    return 0;
+}
+
+void module_register (void)
+{
+    plugin_register_init ("cputemp", init);
+    plugin_register_read ("cputemp", temp_read);
+    return;
+}
