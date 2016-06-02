--- grub-core/partmap/gpt.c.orig	2014-10-20 16:16:07 UTC
+++ grub-core/partmap/gpt.c
@@ -37,6 +37,7 @@ static const grub_gpt_part_type_t grub_g
 
 #ifdef GRUB_UTIL
 static const grub_gpt_part_type_t grub_gpt_partition_type_bios_boot = GRUB_GPT_PARTITION_TYPE_BIOS_BOOT;
+static const grub_gpt_part_type_t grub_gpt_partition_type_freebsd_boot = GRUB_GPT_PARTITION_TYPE_FREEBSD_BOOT;
 #endif
 
 /* 512 << 7 = 65536 byte sectors.  */
@@ -155,7 +156,8 @@ find_usable_region (grub_disk_t disk __a
   disk->partition = p2;
 
   /* If there's an embed region, it is in a dedicated partition.  */
-  if (! grub_memcmp (&gptdata.type, &grub_gpt_partition_type_bios_boot, 16))
+  if (! grub_memcmp (&gptdata.type, &grub_gpt_partition_type_bios_boot, 16) ||
+      ! grub_memcmp (&gptdata.type, &grub_gpt_partition_type_freebsd_boot, 16))
     {
       ctx->start = p->start;
       ctx->len = p->len;
