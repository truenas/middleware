// FREENAS-SERVER CONFIGURATION

"use strict";

var chalk = require("chalk");

// SSH VARIABLES
var pkgTranslations = {
    "node"  : "www/node"
  , "npm"   : "www/npm"
  , "g++"   : "lang/gcc"
  , "gmake" : "devel/gmake"
};


// SSH COMMAND HELPERS
// Install pkgng packages not found in path
function checkAndInstall( command, response, sshObj ) {
  if ( response.indexOf( "Command not found" ) !== -1 ) {
    if ( command === "g++" ) {
      // Need to symlink g++ generic to specific version
      sshObj.commands.unshift( "ln -s /usr/local/bin/g++48 /usr/local/bin/g++" );
      // FIXME: contextify's developer messed up and is looking for a bin
      // called 'c++', when he wanted 'g++'. I hate node developers so much.
      sshObj.commands.unshift( "ln -s /usr/local/bin/g++ /usr/local/bin/c++" );
    }

    sshObj.commands.unshift(
        "msg:" + chalk.bold( "Installing " + command + " (as " + pkgTranslations[command] + ")" )
      , "env ASSUME_ALWAYS_YES=YES pkg install " + pkgTranslations[command]
      , "msg:" + chalk.green( command + " is now installed" )
    );
  } else {
    sshObj.commands.unshift( "msg:" + chalk.green( command + " is already installed" ) );
  }
}

// Install any global NPM packages not found in path
function globalNPMInstall( command, response, sshObj ) {
  if ( response.indexOf( "Command not found" ) !== -1 ) {
    sshObj.commands.unshift(
        "msg:" + chalk.bold( "Installing the NPM package '" + command + "'' globally" )
      , "npm install " + command + " -g"
      , "msg:" + chalk.green( command + " is now installed" )
    );
  } else {
    sshObj.commands.unshift( "msg:" + chalk.green( "The NPM package '" + command + "' is already installed" ) );
  }
}


module.exports = function( grunt ) {
  var commonCommands = {};

  if ( grunt.config( ["freenasVersion"] ) === 10 ) {
    commonCommands = {
        startServer   : "/usr/sbin/service gui start"
      , stopServer    : "/usr/sbin/service gui stop"
      , restartServer : "/usr/sbin/service gui restart"
    };
  } else {
    commonCommands = {
        startServer   : "forever start -a -l forever.log -o out.log -e err.log app/server.js"
      , stopServer    : "forever stopall"
      , restartServer : "forever restart app/server.js"
    };
  }

  // FIXME: This dummy command exists solely because of a bug in ssh2shell
  // which causes an unhandled exception when msg is the last item push()'d
  function ssh2DummyFunction( sshObj ) {
    sshObj.commands.push(":");
  }

  // Output the server's address, neatly formatted
  function printServerAddress( sshObj, command, response ) {
    // TODO: This function needs to be refactored
    var hostAddress = "  " + grunt.config( ["freenasConfig"] )["remoteHost"];
    if ( grunt.config( ["freenasVersion"] ) < 10 ) {
      hostAddress += ":" + grunt.config( ["env"] )["port"];
    }
    hostAddress += "  ";

    var spacer = "  ";
    var vert   = "//";
    var horiz  = function( innerstring ) {
      return vert + new Array( innerstring.length + ( spacer.length * 2 ) + 1 ).join("/") + vert;
    };

    if ( response.indexOf( "error" ) !== -1 ) {
      var message = "Server did not start!";

      console.log( chalk.bgRed( horiz( message ) ) );
      console.log( chalk.bgRed( vert ) + spacer + message + spacer + chalk.bgRed( vert ) );
      console.log( chalk.bgRed( horiz( message ) ) );
      console.log( "\n\n" + response + "\n\n");

      grunt.fatal( "The remote GUI webserver could not be started" );
    } else {
      sshObj.commands.push(
          "msg:Server now running at this address:"
        , "msg:" + chalk.bgGreen( horiz( hostAddress ) )
        , "msg:" + chalk.bgGreen( vert ) + spacer + hostAddress + spacer + chalk.bgGreen( vert )
        , "msg:" + chalk.bgGreen( horiz( hostAddress ) )
      );
    }
  }

  // FREENAS SERVER SCRIPTS
  // These constructors define commands which may be run on FreeNAS via SSH

  // Start or restart the server
  // TODO: Switch to local npm deployment model
  this["start"] = function() {
    this.commands = [
        "cd /usr/local/www/gui"
      , "npm install --production"
      , "/usr/sbin/service gui restart"
    ];

    this.onCommandComplete = function( command, response, sshObj ) {
      switch( command ) {
        case "npm install --production":
          sshObj.commands.unshift( "msg:" + chalk.green( "npm packages are up to date" ) );
          break;

        case "/usr/sbin/service gui restart":
            printServerAddress( sshObj, command, response );
            ssh2DummyFunction( sshObj );
          break;
      }
    };
  };

  this["start-legacy"] = function() {
    this.commands = [
        "mount -uw /"
      , ( "setenv PORT " + grunt.config( ["env"] )["port"] )
      , ( "setenv FOREVER_ROOT " + grunt.config( ["freenasConfig"] )["freeNASPath"] + ".forever" )
      , ( "cd " + grunt.config( ["freenasConfig"] )["freeNASPath"] )
      , ( "msg:" + chalk.cyan( "running `npm install --production`" ) )
      , "npm install --production"
      , ( "msg:" + chalk.cyan( "Checking status of FreeNAS GUI webserver" ) )
      , "forever list"
    ];

    this.onCommandComplete = function( command, response, sshObj ) {
      switch( command ) {
        case "mount -uw /":
          sshObj.commands.unshift( "msg:" + chalk.green( "filesystem mounted successfully" ) );
          break;

        case ( "setenv PORT " + grunt.config( ["env"] )["port"] ):
          sshObj.commands.unshift( "msg:" + chalk.cyan( "Set $PORT environment variable to " + grunt.config( ["env"] )["port"]) );
          break;

        case ( "setenv FOREVER_ROOT " + grunt.config( ["freenasConfig"] )["freeNASPath"] + ".forever" ):
          sshObj.commands.unshift( "msg:" + chalk.cyan( "Set $FOREVER_ROOT environment variable to " + grunt.config( ["freenasConfig"] )["freeNASPath"] + ".forever" ) );
          break;

        case ( "cd " + grunt.config( ["freenasConfig"] )["freeNASPath"] ):
          sshObj.commands.unshift( "msg:" + chalk.cyan( "Changed directory to " + grunt.config( ["freenasConfig"] )["freeNASPath"] ) );
          break;

        case "npm install --production":
          sshObj.commands.unshift( "msg:" + chalk.green( "npm packages are up to date" ) );
          break;

        case "forever list":
          if ( response.indexOf( "No forever processes running" ) !== -1 ) {
            sshObj.commands.push(
                "killall node" // Make sure no orphan processes are running
              , "msg:" + chalk.cyan( "Starting FreeNAS 10 GUI server" )
              , commonCommands["startServer"]
            );
          } else {
            sshObj.commands.push(
                "msg:" + chalk.green( "FreeNAS 10 GUI was already running" )
              , "msg:" + chalk.cyan( "Restarting server" )
              , commonCommands["restartServer"]
            );
          }
          ssh2DummyFunction( sshObj );
          break;

        case commonCommands["startServer"]:
        case commonCommands["restartServer"]:
            printServerAddress( sshObj, command, response );
            ssh2DummyFunction( sshObj );
          break;
      }
    };
  };

  // Shut down the Forever server
  this["stop"] = function() {
    this.commands = [
      , ( "msg:" + chalk.cyan( "Stopping FreeNAS GUI webserver" ) )
      , commonCommands["stopServer"]
    ];
  };

  this["stop-legacy"] = function() {
    this.commands = [
      , ( "msg:" + chalk.cyan( "Stopping FreeNAS GUI webserver" ) )
      , commonCommands["stopServer"]
    ];
  };

  this["bootstrap"] = function() {
    this.commands = [
        "msg:" + chalk.cyan( "Now checking FreeNAS 10 environment and installing any required software" )
      , "rehash"         // Update path
      // Check if pkg(8) has been initialized
      , "cat /usr/local/etc/pkg/repos/FreeBSD.conf"
      // pkgng packages
      , "which gmake"    // Check if gmake is installed
      , "which g++"      // Check if g++ (or Clang) is installed
      , "which npm"      // Check if npm is installed TODO: remove this
      , "rehash"         // Update path
      // npm pacakages
      , "npm -v"         // Update npm to latest; port is usually out of date
      , "rehash"         // Update path
      , "npm config set cache /usr/local/www/gui/.npm-cache --global"
      , "cd /usr/include/"
    ];
    this.onCommandComplete = function( command, response, sshObj ) {
      switch ( command ) {
        case "cat /usr/local/etc/pkg/repos/FreeBSD.conf":
          if ( response.indexOf( "enabled: no" ) !== -1 ) {
            sshObj.commands.unshift(
                "msg:" + chalk.cyan( "Enabling pkg(8)" )
              , "sed -i -e 's/no/yes/' /usr/local/etc/pkg/repos/FreeBSD.conf"
            );
          } else {
            sshObj.commands.unshift( "msg:" + chalk.green( "pkg(8) is already enabled" ) );
          }
          break;

        case "which gmake":
          checkAndInstall( "gmake", response, sshObj );
          break;

        case "which g++":
          checkAndInstall( "g++", response, sshObj );
          break;

        case "which npm":
          checkAndInstall( "npm", response, sshObj );
          break;

        case "npm -v":
          if ( response.search("2.") !== -1 ) {
            sshObj.commands.unshift( "msg:" + chalk.green( "npm looks current" ) );
          } else {
            sshObj.commands.unshift(
                "msg:Updating npm to latest version."
              , "npm update -g npm"
              , "npm -v"
            );
          }
          break;

        case "cd /usr/include/":
          if ( response.search("No such file or directory") !== -1 ) {
            sshObj.commands.push("msg:No header files were found in /usr/include");
            sshObj.commands.push("mkdir -p ~/.tmp/headerfiles/");
            grunt.task.run( "freenas-server:headerfiles-copy" );
            grunt.task.run( "freenas-server:headerfiles-unpack" );
          } else {
            sshObj.commands.push("msg:" + chalk.green( "Header files found in /usr/include" ) );
            ssh2DummyFunction( sshObj );
          }
          break;
      }
    };
  };

  this["bootstrap-legacy"] = function() {
    this.commands = [
        "msg:" + chalk.cyan( "Now checking FreeNAS 9 environment and installing any required software" )
      , "mount -uw /"    // Mount root filesystem as read-write
      , "rehash"         // Update path
      , "pkg -N"         // Check if pkg(8) has been initialized
      // pkgng packages
      , "which gmake"    // Check if gmake is installed
      , "which g++"      // Check if g++ (or Clang) is installed
      , "which node"     // Check if node is installed
      , "which npm"      // Check if npm is installed
      , "rehash"         // Update path
      // npm pacakages
      , "npm -v"         // Update npm to latest; port is usually out of date
      , "which forever"  // Check if forever is installed
      , "rehash"         // Update path
      // Make any directories specified by user, guarantee path exists
      , "mkdir -p " + grunt.config( ["freenasConfig"] )["freeNASPath"]
      // Relocate npm cache to user dir; don't fill up / with caches
      , "mkdir -p " + grunt.config( ["freenasConfig"] )["freeNASPath"] + ".npm-cache"
      , "npm config set cache " + grunt.config( ["freenasConfig"] )["freeNASPath"] + ".npm-cache --global"
      , "cd /usr/include/"
    ];
    this.onCommandComplete = function( command, response, sshObj ) {
      switch ( command ) {
        case "pkg -N":
          if ( response.indexOf( "pkg is not installed" ) !== -1 ) {
            sshObj.commands.unshift(
                "msg:System predates FreeNAS 9.3"
              , "msg:"+ chalk.bold( "Updating and bootstrapping pkg(8)" )
              , "env ASSUME_ALWAYS_YES=YES pkg bootstrap"
            );
          } else {
            // If FreeNAS 9.3 version of pkgng is being used, this directory
            // should exist. Using that as a truth test for >9.2
            sshObj.commands.unshift( "ls /usr/local/etc/pkg" );
          }
          break;

        case "ls /usr/local/etc/pkg":
          if ( response.indexOf( "repos" ) !== -1 ) {
            sshObj.commands.unshift(
                "msg:System is newer than FreeNAS 9.2"
              , "msg:" + chalk.bold( "Converting iXsystems pkg system to bootstrapped pkg(8)" )
              // Remove iXsystems-specific pkg files
              , "msg:" + chalk.cyan( "Removing iXsystems package manger" )
              , "rm -rf /usr/local/etc/pkg"
              // Ensure key dirs exist
              , "msg:" + chalk.cyan( "Getting current pkg keys" )
              , "mkdir -p /usr/share/keys/pkg/trusted /usr/share/keys/pkg/revoked"
              , "wget --no-check-certificate https://svn0.us-west.freebsd.org/base/head/share/keys/pkg/trusted/pkg.freebsd.org.2013102301 -O /usr/share/keys/pkg/trusted/pkg.freebsd.org.201310230"
              // Manually install pkg(8)
              , "msg:" + chalk.cyan( "Obtaining newest version of pkg(8)" )
              , "cd /tmp && wget http://pkg.freebsd.org/freebsd:9:x86:64/latest/All/pkg-1.3.7.txz"
              , "msg:" + chalk.cyan( "Installing pkg(8)" )
              , "tar xf pkg-1.3.7.txz -C /"
              // Remove existing db to clear the upgrade
              , "msg:" + chalk.cyan( "Removing old pkg database" )
              , "rm -rf /var/db/pkg"
              , "msg:" + chalk.cyan( "Running pkg upgrade" )
              , "pkg upgrade"
            );
          } else {
            sshObj.commands.unshift( "msg:" + chalk.green( "pkg(8) has already been bootstrapped and is installed" ) );
          }
          break;

        case "which gmake":
          checkAndInstall( "gmake", response, sshObj );
          break;

        case "which g++":
          checkAndInstall( "g++", response, sshObj );
          break;

        case "which node":
          checkAndInstall( "node", response, sshObj );
          break;

        case "which npm":
          checkAndInstall( "npm", response, sshObj );
          break;

        case "npm -v":
          if ( response.search("2.1.") !== -1 ) {
            sshObj.commands.unshift( "msg:" + chalk.green( "npm looks current" ) );
          } else {
            sshObj.commands.unshift(
                "msg:Updating npm to latest version."
              , "npm update -g npm"
              , "npm -v"
            );
          }
          break;

        case "which forever":
          globalNPMInstall( "forever", response, sshObj );
          break;

        case "cd /usr/include/":
          if ( response.search("No such file or directory") !== -1 ) {
            sshObj.commands.push("msg:No header files were found in /usr/include");
            sshObj.commands.push("mkdir -p ~/.tmp/headerfiles/");
            grunt.task.run( "freenas-server:headerfiles-copy" );
            grunt.task.run( "freenas-server:headerfiles-unpack" );
          } else {
            sshObj.commands.push("msg:" + chalk.green( "Header files found in /usr/include" ) );
            ssh2DummyFunction( sshObj );
          }
          break;
      }
    };
  };

  this["headerfiles-copy"] = {
    // No options needed
  };

  this["headerfiles-unpack"] = function() {
    this.commands = [
        "msg:Unpacking header files into /usr/include/"
      , "mkdir -p /usr/include/"
      , "tar -C /usr/include/ -xvzf /root/.tmp/headerfiles/headerfiles.tar.gz"
    ];
  };
};