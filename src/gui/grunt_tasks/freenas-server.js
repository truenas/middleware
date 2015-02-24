// FREENAS-SERVER
// Connect to the remote FreeNAS server and perform various operations on it.
// This task bootstraps the development environment, SCPs certain files, and
// manages the lifecycle of the remote webserver.

"use strict";

// Node builtins
var fs   = require("fs");
var path = require("path");
var exec = require("child_process").exec;

// NPM packages
var _          = require("lodash");
var chalk      = require("chalk");
var SSH2Shell  = require("ssh2shell");
var scpClient  = require("scp2").Client;

// Platform data
var currentPlatform = process.platform;
var isWindows       = ( currentPlatform === "win32" );


module.exports = function(grunt) {
  grunt.registerMultiTask( "freenas-server", function() {
    var asyncDone  = this.async();

    // Object will be assigned commands based on this.target
    var SSHOptions = function () {
      this.msg = {
          send: function( message ) {
            console.log( message );
          }
      };
      this.verbose       = false;
      this.debug         = false;
      this.idleTimeOut   = 1000000;
      this.readyMessage  = "ssh: Connection ready";
      this.closedMessage = "ssh: Connection closed";
      this.onCommandProcessing = function( command, response, sshObj, stream ) {
        // switch( command ), if needed
      };
      this.onCommandComplete = function( command, response, sshObj ) {
        // switch( command ), if needed
      };
      this.onEnd = function( sessionText, sshObj ) {
        sshObj.exitCommands.push("exit");
        asyncDone();
      };
      this.server = {
          host       : grunt.config( ["freenasConfig"] )["remoteHost"]
        , port       : grunt.config( ["freenasConfig"] )["sshPort"]
        , userName   : "root"
      };
      this.connectedMessage = chalk.green( "Successfully connected as root@" + grunt.config( ["freenasConfig"] )["remoteHost"] );

      // TODO: Allow private key passphrase
      // Modify options object with keypair path or password
      if ( grunt.config( ["freenasConfig"] )["authType"] === "useKeypair" ) {
        this.server["privateKey"] = fs.readFileSync( grunt.config( ["freenasConfig"] )["keyPath"] );
      } else {
        this.server["password"] = grunt.config( ["freenasConfig"] )["rootPass"];
        console.log( chalk.yellow( "\nWARNING: Using password authentication will only work for configuration of the FreeNAS environment, and is not permitted for actual development.\n" ) );
      }
    };


    // TODO: move into common
    function endOnFatal( errorMsg ) {
        grunt.fail.fatal( errorMsg ? errorMsg : null );
        grunt.task.clearQueue();
        asyncDone();
    }


    // Make sure host is reachable
    // TODO: move into common
    function pingFreeNAS() {
      exec("ping " + ( isWindows ? "-n" : "-c" ) + " 1 " + grunt.config( ["freenasConfig"] )["remoteHost"], function(error, stdout, stderr) {
        if (error) {
          endOnFatal( "Host '" + grunt.config( ["freenasConfig"] )["remoteHost"] + "' is unreachable." );
        }
      });
    }

    // CONNECT TO FREENAS
    // Load Grunt config options into SSH options object once they're available
    // Prevents them from resolving as 'null' when the freenas-server task loads

    // Open an SSH connection to FreeNAS and run requested commands
    function sshToFreeNAS( statusMsg, OptionsObj ) {
      // Load the config defaults, now that the config file has been loaded
      var ssh2shellOptions = _.assign( new SSHOptions(), new OptionsObj() );

      // Print status message, if provided
      if ( statusMsg ) {
        console.log( "STATUS: " + statusMsg );
      }

      // Connect to FreeNAS and perform the requested operation
      console.log( chalk.cyan( "Connecting to " + grunt.config( ["freenasConfig"] )["remoteHost"] ) );
      var SSH = new SSH2Shell( ssh2shellOptions );
      SSH.connect();
    }

    // SCP requested files to FreeNAS
    function scpToFreeNAS( statusMsg, fileName, localPath, remotePath ) {
      var configOptions = {
          port     : grunt.config( ["freenasConfig"] )["sshPort"]
        , host     : grunt.config( ["freenasConfig"] )["remoteHost"]
        , username : "root"
      };

      // Modify options object with keypair path or password
      if ( grunt.config( ["freenasConfig"] )["authType"] === "useKeypair" ) {
        configOptions["privateKey"] = fs.readFileSync( grunt.config( ["freenasConfig"] )["keyPath"] );
      } else {
        configOptions["password"] = grunt.config( ["freenasConfig"] )["rootPass"];
        console.log( chalk.yellow( "\nWARNING: Using password authentication will only work for configuration of the FreeNAS environment, and is not permitted for actual development.\n" ) );
      }

      // Print status message, if provided
      if ( statusMsg ) {
        console.log( "STATUS: " + statusMsg );
      }

      // Connect to FreeNAS and copy the requested file
      console.log( chalk.cyan( "Connecting to " + grunt.config( ["freenasConfig"] )["remoteHost"] ) );
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


    // Make sure the config file exists
    if ( grunt.config( ["freenasConfig"] )["notConfigured"] ) {
      endOnFatal( "No configuration file found." );
    }

    // Make sure the host is up
    pingFreeNAS();

    // Load config for the specific task
    switch ( this.target ) {
      case "bootstrap":
        sshToFreeNAS( "Checking FreeNAS 10 environment", this.data );
        break;

      case "headerfiles-copy":
        scpToFreeNAS(
            "Copying FreeBSD header files to FreeNAS"
          , "headerfiles.tar.gz"
          , "./assets/"
          , "/root/.tmp/headerfiles/"
        );
        break;

      case "headerfiles-unpack":
        sshToFreeNAS( "Unpacking header files into /usr/include/", this.data );
        break;

      case "start":
        sshToFreeNAS( "Starting remote FreeNAS GUI server", this.data );
        break;
    }
  });
};