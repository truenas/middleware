--- setup.py.orig	2015-08-06 18:12:14.000000000 -0700
+++ setup.py	2015-08-06 18:14:36.000000000 -0700
@@ -49,7 +49,8 @@
 ]
 
 system_includes = [os.path.expandvars(x) for x in system_includes]
-freebsd_version = int(subprocess.check_output("uname -K", shell=True).strip())
+# Stupid hack for freenas freenas 9.3's trueos
+freebsd_version = 1000000
 
 setup(
     name='libzfs',
