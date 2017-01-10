--- toolbox/toolboxcmd-shrink.c.orig	2013-09-23 17:51:10.000000000 +0200
+++ toolbox/toolboxcmd-shrink.c	2014-11-25 17:57:44.000000000 +0100
@@ -391,7 +391,7 @@ ShrinkDoWipeAndShrink(char *mountPoint, 
     * Verify that wiping/shrinking are permitted before going through with the
     * wiping operation.
     */
-   if (!ShrinkGetWiperState() == WIPER_ENABLED && !Wiper_IsWipeSupported(part)) {
+   if (ShrinkGetWiperState() != WIPER_ENABLED && !Wiper_IsWipeSupported(part)) {
       g_debug("%s cannot be wiped / shrunk\n", mountPoint);
       ToolsCmd_PrintErr("%s",
                         SU_(disk.shrink.disabled, SHRINK_DISABLED_ERR));
