--- lib/misc/util_misc.c.orig	2009-04-14 02:38:09.000000000 +0200
+++ lib/misc/util_misc.c	2009-04-14 02:39:00.000000000 +0200
@@ -292,7 +292,7 @@
    return (strcmp(path1, path2) == 0);
 #elif defined(_WIN32)
    return (_stricmp(path1, path2) == 0);
-#elif defined(__APPLE__)
+#elif defined(__APPLE__) || defined(__FreeBSD__)
    return (strcasecmp(path1, path2) == 0);
 #else
    NOT_IMPLEMENTED();
@@ -319,7 +319,7 @@
 Bool
 Util_IsAbsolutePath(const char *path)  // IN: path to check
 {
-#if defined(__linux__) || defined(__APPLE__)
+#if defined(__linux__) || defined(__APPLE__) || defined(__FreeBSD__)
    // path[0] is valid even for the empty string.
    return path && path[0] == DIRSEPC;
 #elif defined(_WIN32)
