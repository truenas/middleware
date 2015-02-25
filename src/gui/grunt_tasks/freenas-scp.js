// FREENAS SCP
// Tasks for copying files to the remote FreeNAS instance using SCP.

"use strict";

// Node builtins
var fs   = require("fs");
var path = require("path");

// NPM packages
var chalk     = require("chalk");
var scpClient = require("scp2").Client;

module.exports = function( grunt ) {
  grunt.registerMultiTask( "freenas-scp", function() {
    var asyncDone  = this.async();

    // SCP requested files to FreeNAS
    function scpToFreeNAS( statusMsg, fileName, localPath, remotePath ) {
      var configOptions = {
          port     : grunt.config( ["freeNASConfig"] )["sshPort"]
        , host     : grunt.config( ["freeNASConfig"] )["remoteHost"]
        , username : "root"
      };

      // Modify options object with keypair path or password
      if ( grunt.config( ["freeNASConfig"] )["authType"] === "useKeypair" ) {
        configOptions["privateKey"] = fs.readFileSync( grunt.config( ["freeNASConfig"] )["keyPath"] );
      } else {
        configOptions["password"] = grunt.config( ["freeNASConfig"] )["rootPass"];
        console.log( chalk.yellow( "\nWARNING: Using password authentication will only work for configuration of the FreeNAS environment, and is not permitted for actual development.\n" ) );
      }

      // Print status message, if provided
      if ( statusMsg ) {
        console.log( "STATUS: " + statusMsg );
      }

      // Connect to FreeNAS and copy the requested file
      console.log( chalk.cyan( "Connecting to " + grunt.config( ["freeNASConfig"] )["remoteHost"] ) );
      var client = new scpClient( configOptions );

      client.upload(
          path.join( __dirname, ( localPath + fileName ) )
        , path.join( remotePath + fileName )
        , function( error ) {
            if ( error ) {
              grunt.fail.fatal( error );
              asyncDone();
            } else {
              console.log( chalk.green( "Upload successful" ) );
              asyncDone();
              client.close();
            }
          }
      );
    }

    switch ( this.target ) {
      case "header-files":
        scpToFreeNAS(
            "Copying FreeBSD header files to FreeNAS"
          , "headerfiles.tar.gz"
          , "./assets/"
          , "/root/.tmp/headerfiles/"
        );
        break;
    }
  });

};
