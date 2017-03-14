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

--- Lib/distutils/tests/test_install_lib.py.orig	2015-12-07 01:39:07 UTC
+++ Lib/distutils/tests/test_install_lib.py
@@ -64,11 +64,15 @@ class InstallLibTestCase(support.Tempdir
         cmd.distribution.ext_modules = [Extension('foo', ['xxx'])]
         cmd.distribution.packages = ['spam']
         cmd.distribution.script_name = 'setup.py'
+        
+        # Create rubbish, uncompilable file
+        f = os.path.join(project_dir, 'spam', 'rubbish.py')
+        self.write_file(f, 'rubbish()')
 
         # get_outputs should return 4 elements: spam/__init__.py and .pyc,
-        # foo.import-tag-abiflags.so / foo.pyd
+        # foo.import-tag-abiflags.so / foo.pyd and rubbish.py (no .pyc)
         outputs = cmd.get_outputs()
-        self.assertEqual(len(outputs), 4, outputs)
+        self.assertEqual(len(outputs), 5, outputs)
 
     def test_get_inputs(self):
         project_dir, dist = self.create_dist()
