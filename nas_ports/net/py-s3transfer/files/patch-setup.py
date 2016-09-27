--- setup.py.orig	2016-08-06 10:02:48 UTC
+++ setup.py
@@ -14,6 +14,10 @@ requires = [
     'botocore>=1.3.0,<2.0.0',
 ]
 
+tests_require = [
+    'nose>=1.3.3',
+    'mock>=1.3.0',
+]
 
 if sys.version_info[0] == 2:
     # concurrent.futures is only in python3, so for
@@ -41,6 +45,8 @@ setup(
         ':python_version=="2.6" or python_version=="2.7"': [
             'futures>=2.2.0,<4.0.0']
     },
+    tests_require=tests_require,
+    test_suite='nose.collector',
     license="Apache License 2.0",
     classifiers=(
         'Development Status :: 1 - Planning',
