--- setup.py.orig	2016-08-01 02:01:42.000000000 -0700
+++ setup.py	2016-08-01 02:03:09.000000000 -0700
@@ -24,10 +24,7 @@
 # SUCH DAMAGE.
 #
 
-import Cython.Compiler.Options
-Cython.Compiler.Options.annotate = True
 import os
-import subprocess
 from distutils.core import setup
 from Cython.Distutils.extension import Extension
 from Cython.Distutils import build_ext
@@ -55,13 +52,11 @@
 ]
 
 system_includes = [os.path.expandvars(x) for x in system_includes]
-freebsd_version = int(subprocess.check_output("uname -K", shell=True).strip())
+# Stupid hack for freenas freenas 9.3's trueos
+freebsd_version = 1000000
 
 setup(
     name='libzfs',
     version='1.0',
-    packages=[''],
-    package_data={'': ['*.html', '*.c']},
     cmdclass={'build_ext': build_ext},
     ext_modules=[
         Extension(
