--- ./test/bench/shootout/timing.sh.orig	2013-06-09 23:33:01.405924747 +1000
+++ ./test/bench/shootout/timing.sh	2013-06-09 23:33:16.526347653 +1000
@@ -81,7 +81,7 @@
 	$1
 	shift
 	
-	echo $((time -p $* >/dev/null) 2>&1) | awk '{print $4 "u " $6 "s " $2 "r"}'
+	echo $( (time -p $* >/dev/null) 2>&1) | awk '{print $4 "u " $6 "s " $2 "r"}'
 }
 
 fasta() {
