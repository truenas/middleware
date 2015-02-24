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

// Create a "msg:" string readable by ssh2shell
function sshMsg( string, chalkClass ) {
  return ( "msg:" + chalkClass ? chalk[ chalkClass ]( string ) : string );
}

// Test that a response was issued, and that it contains the provided string
function responseContains( response, testString ) {
  console.log( "response is string: " + typeof response === "string" );
  console.log( "response contains '" + testString + "': " + response.indexOf( testString ) !== -1 );
  if ( typeof response === "string" && response.indexOf( testString ) !== -1 ) {
    return true;
  } else {
    return false;
  }
}

// Install pkgng packages not found in path
function checkAndInstall( command, response, sshObj ) {
  if ( responseContains( response, "Command not found" ) ) {
    if ( command === "g++" ) {
      // Need to symlink g++ generic to specific version
      sshObj.commands.unshift( "ln -s /usr/local/bin/g++48 /usr/local/bin/g++" );
      // FIXME: contextify's developer messed up and is looking for a bin
      // called 'c++', when he wanted 'g++'. I hate node developers so much.
      sshObj.commands.unshift( "ln -s /usr/local/bin/g++ /usr/local/bin/c++" );
    }

    sshObj.commands.unshift(
        sshMsg( "Installing " + command + " (as " + pkgTranslations[command] + ")", "bold" )
      , "env ASSUME_ALWAYS_YES=YES pkg install " + pkgTranslations[command]
      , sshMsg( command + " is now installed", "green" )
    );
  } else {
    sshObj.commands.unshift( sshMsg( command + " is already installed", "green" ) );
  }
}

// Install any global NPM packages not found in path
// TODO: This is currently not in use, and could be removed.
function globalNPMInstall( command, response, sshObj ) {
  if ( responseContains( response, "Command not found" ) ) {
    sshObj.commands.unshift(
        sshMsg( "Installing the NPM package '" + command + "'' globally", "bold" )
      , "npm install " + command + " -g"
      , sshMsg( command + " is now installed", "green" )
    );
  } else {
    sshObj.commands.unshift( sshMsg( "The NPM package '" + command + "' is already installed", "green" ) );
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

    if ( responseContains( response, "error" ) ) {
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
          sshObj.commands.unshift( sshMsg( "npm packages are up to date", "green" ) );
          break;

        case "/usr/sbin/service gui restart":
            printServerAddress( sshObj, command, response );
            ssh2DummyFunction( sshObj );
          break;
      }
    };
  };

  // Shut down the Forever server
  this["stop"] = function() {
    this.commands = [
      , ( sshMsg( "Stopping FreeNAS GUI webserver", "cyan" ) )
      , commonCommands["stopServer"]
    ];
  };

  this["bootstrap"] = function() {
    this.commands = [
        sshMsg( "Now checking FreeNAS 10 environment and installing any required software", "cyan" )
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
          if ( responseContains( response, "enabled: no" ) ) {
            sshObj.commands.unshift(
                sshMsg( "Enabling pkg(8)", "cyan" )
              , "sed -i -e 's/no/yes/' /usr/local/etc/pkg/repos/FreeBSD.conf"
            );
          } else {
            sshObj.commands.unshift( sshMsg( "pkg(8) is already enabled", "green" ) );
            ssh2DummyFunction( sshObj );
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
          if ( responseContains( response,"2.") ) {
            sshObj.commands.unshift( sshMsg( "npm is at least version 2.0", "green" ) );
          } else {
            sshObj.commands.unshift(
                sshMsg( "msg:Updating npm to latest version." )
              , "npm update -g npm"
              , "npm -v"
            );
          }
          break;

        case "cd /usr/include/":
          if ( responseContains( response, "No such file or directory") ) {
            sshObj.commands.push(
                "msg:No header files were found in /usr/include"
              , "mkdir -p ~/.tmp/headerfiles/"
            );
            grunt.task.run( "freenas-server:headerfiles-copy" );
            grunt.task.run( "freenas-server:headerfiles-unpack" );
          } else {
            sshObj.commands.push( sshMsg( "Header files found in /usr/include", "green" ) );
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