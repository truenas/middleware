--- include/grub/gpt_partition.h.orig	2014-03-03 16:00:26 UTC
+++ include/grub/gpt_partition.h
@@ -43,6 +43,14 @@ typedef struct grub_gpt_part_type grub_g
     { 0x74, 0x4e, 0x65, 0x65, 0x64, 0x45, 0x46, 0x49 } \
   }
 
+#define GRUB_GPT_PARTITION_TYPE_FREEBSD_BOOT \
+  { grub_cpu_to_le32_compile_time (0x83bd6b9d), \
+      grub_cpu_to_le16_compile_time (0x7f41), \
+      grub_cpu_to_le16_compile_time (0x11dc),	       \
+    { 0xbe, 0x0b, 0x00, 0x15, 0x60, 0xb8, 0x4f, 0x0f } \
+  }
+
+
 #define GRUB_GPT_PARTITION_TYPE_LDM \
   { grub_cpu_to_le32_compile_time (0x5808C8AAU),\
       grub_cpu_to_le16_compile_time (0x7E8F), \
