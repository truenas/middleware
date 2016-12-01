--- version/version.go.orig	2016-11-10 20:33:01 UTC
+++ version/version.go
@@ -13,8 +13,8 @@ var (
 
 	// Release versions of the build. These will be filled in by one of the
 	// build tag-specific files.
-	Version           = "unknown"
-	VersionPrerelease = "unknown"
+	Version           = "0.7.1"
+	VersionPrerelease = ""
 )
 
 // GetHumanVersion composes the parts of the version in a way that's suitable
