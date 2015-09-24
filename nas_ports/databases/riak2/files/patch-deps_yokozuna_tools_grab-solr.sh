--- deps/yokozuna/tools/grab-solr.sh.orig	2015-04-15 02:24:04.000000000 +1000
+++ deps/yokozuna/tools/grab-solr.sh	2015-09-24 10:46:04.504531298 +1000
@@ -14,10 +14,10 @@
     cd tools
 fi
 
-PRIV_DIR=../priv
+PRIV_DIR=%%YOKOZUNA%%/priv
 CONF_DIR=$PRIV_DIR/conf
 SOLR_DIR=$PRIV_DIR/solr
-BUILD_DIR=../build
+BUILD_DIR=%%BUILD_DIR%%
 VSN=solr-4.7.0-yz-1
 FILENAME=$VSN.tgz
 TMP_DIR=/var/tmp/yokozuna
@@ -32,58 +32,11 @@
     test -e $SOLR_DIR/start.jar
 }
 
-download()
-{
-    if which wget > /dev/null; then
-        wget --no-check-certificate --progress=dot:mega $1
-    elif which curl > /dev/null; then
-        curl --insecure --progress-bar -O $1
-    elif which fetch > /dev/null; then
-        fetch --no-verify-peer $1
-    fi
-}
-
-get_solr()
-{
-        if [ -z ${SOLR_PKG_DIR+x} ]
-        then
-            if [ -e $TMP_FILE ]; then
-                echo "Using cached copy of Solr $TMP_FILE"
-                ln -s $TMP_FILE $FILENAME
-            else
-                echo "Pulling Solr from S3"
-                download "http://s3.amazonaws.com/files.basho.com/solr/$FILENAME"
-                if [ -d $TMP_DIR ]; then
-                    cp $FILENAME $TMP_DIR
-                else
-                    mkdir $TMP_DIR
-                    cp $FILENAME $TMP_DIR
-                fi
-            fi
-        else
-            # This is now obsolete thanks to implicit caching above
-            # but will leave in for now as to not break anyone.
-            echo "Using local copy of Solr $SOLR_PKG_DIR/$FILENAME"
-            cp $SOLR_PKG_DIR/$FILENAME ./
-        fi
-        tar zxf $FILENAME
-}
-
 if ! check_for_solr
 then
 
-    echo "Create dir $BUILD_DIR"
-    if [ ! -e $BUILD_DIR ]; then
-        mkdir $BUILD_DIR
-    fi
-
     cd $BUILD_DIR
 
-    if [ ! -e $SRC_DIR ]
-    then
-        get_solr
-    fi
-
     echo "Creating Solr dir $SOLR_DIR"
 
     # Explicitly copy files needed rather than copying everything and
@@ -108,7 +61,7 @@
     echo "Solr dir created successfully"
 fi
 
-JAVA_LIB=../priv/java_lib
+JAVA_LIB=%%YOKOZUNA%%/priv/java_lib
-YZ_JAR_VSN=2
+YZ_JAR_VSN=1
 YZ_JAR_NAME=yokozuna-$YZ_JAR_VSN.jar
 
@@ -118,19 +71,17 @@
     then
         mkdir $JAVA_LIB
     fi
-
-    echo "Downloading $YZ_JAR_NAME"
-    download "http://s3.amazonaws.com/files.basho.com/yokozuna/$YZ_JAR_NAME"
-    mv $YZ_JAR_NAME $JAVA_LIB/$YZ_JAR_NAME
+    echo "Copying $YZ_JAR_NAME"
+    cp %%DISTDIR%%/$YZ_JAR_NAME $JAVA_LIB/$YZ_JAR_NAME
 fi
 
-EXT_LIB=../priv/solr/lib/ext
+EXT_LIB=%%YOKOZUNA%%/priv/solr/lib/ext
 MON_JAR_VSN=1
 MON_JAR_NAME=yz_monitor-$MON_JAR_VSN.jar
 
 if [ ! -e $EXT_LIB/$MON_JAR_NAME ]
 then
     echo "Downloading $MON_JAR_NAME"
-    download "http://s3.amazonaws.com/files.basho.com/yokozuna/$MON_JAR_NAME"
-    mv $MON_JAR_NAME $EXT_LIB/$MON_JAR_NAME
+    echo "Copying $MON_JAR_NAME"
+    cp %%DISTDIR%%/$MON_JAR_NAME $EXT_LIB/$MON_JAR_NAME
 fi
