From 9934ce31b8447667f71c211e559a8de71e8263db Mon Sep 17 00:00:00 2001
From: Brendan Molloy <brendan@bbqsrc.net>
Date: Mon, 4 Jan 2016 23:14:06 +1100
Subject: [PATCH] Check bytecode file actually exists and tests

Should solve issue 20397, where using the --record argument results
in files that failed to generate bytecode files are added to the
record file nonetheless.
---
 Lib/distutils/command/install_lib.py    | 17 +++++++++++++----
 Lib/distutils/tests/test_install_lib.py |  8 ++++++--
 2 files changed, 19 insertions(+), 6 deletions(-)

--- Lib/distutils/command/install_lib.py.orig	2015-12-07 01:39:07 UTC
+++ Lib/distutils/command/install_lib.py
@@ -164,12 +164,21 @@ class install_lib(Command):
             ext = os.path.splitext(os.path.normcase(py_file))[1]
             if ext != PYTHON_SOURCE_EXTENSION:
                 continue
+
             if self.compile:
-                bytecode_files.append(importlib.util.cache_from_source(
-                    py_file, optimization=''))
+                candidate = importlib.util.cache_from_source(
+                    py_file, optimization='')
+
+                if os.path.isfile(candidate):
+                    bytecode_files.append(candidate)
+
             if self.optimize > 0:
-                bytecode_files.append(importlib.util.cache_from_source(
-                    py_file, optimization=self.optimize))
+                candidate = importlib.util.cache_from_source(
+                    py_file, optimization=self.optimize)
+
+                if os.path.isfile(candidate):
+                    bytecode_files.append(candidate)
+
 
         return bytecode_files
 
