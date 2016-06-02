--- include/grub/i386/freebsd_bootinfo.h.orig	2015-06-07 21:44:01 UTC
+++ include/grub/i386/freebsd_bootinfo.h
@@ -0,0 +1,33 @@
+/*
+ *  GRUB  --  GRand Unified Bootloader
+ *  Copyright (C) 2008,2009  Free Software Foundation, Inc.
+ *
+ *  GRUB is free software: you can redistribute it and/or modify
+ *  it under the terms of the GNU General Public License as published by
+ *  the Free Software Foundation, either version 3 of the License, or
+ *  (at your option) any later version.
+ *
+ *  GRUB is distributed in the hope that it will be useful,
+ *  but WITHOUT ANY WARRANTY; without even the implied warranty of
+ *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
+ *  GNU General Public License for more details.
+ *
+ *  You should have received a copy of the GNU General Public License
+ *  along with GRUB.  If not, see <http://www.gnu.org/licenses/>.
+ */
+
+#include <grub/types.h>
+
+#define FREEBSD_BTINFO_FRAMEBUF  0x1005
+
+struct grub_freebsd_btinfo_framebuf {
+  grub_uint64_t        fb_addr;
+  grub_uint64_t        fb_size;
+  grub_int32_t         fb_height;
+  grub_int32_t         fb_width;
+  grub_int32_t         fb_stride;
+  grub_uint32_t        fb_mask_red;
+  grub_uint32_t        fb_mask_green;
+  grub_uint32_t        fb_mask_blue;
+  grub_uint32_t        fb_mask_reserved;
+};
