// SSH-MULTI-EXEC
// Allows the execution of remote SSH commands based on input credentials.

"use strict";

var _     = require("lodash");
var chalk = require("chalk");

// SSH VARIABLES
var pkgTranslations = {
    "node"  : "www/node"
  , "npm"   : "www/npm"
  , "g++"   : "lang/gcc"
  , "gmake" : "devel/gmake"
};

module.exports = function( grunt ) {

  var testResults = {};

  // SSH HELPERS
  // Test that a response was issued, and that it contains the provided string
  function logSshMsg( string, chalkClass ) {
    grunt.log.writeln( "Status: " + ( chalkClass ? chalk[ chalkClass ]( string ) : string ) );
  }

  // Simple truth test to determine if a given stdout response contains the
  // specified word or phrase
  function responseContains( response, testString ) {
    if ( typeof response === "string" && response.indexOf( testString ) !== -1 ) {
      return true;
    } else {
      return false;
    }
  }

  // Output the server's address, neatly formatted
  function printServerAddress( state ) {
    var whitespace = "  ";
    var yAxis      = "//";
    var xAxis;

    var hostAddress = whitespace + grunt.config( ["freeNASConfig"] )["remoteHost"] + whitespace;
    var failMessage = whitespace + "Server did not start!" + whitespace;


    var repChar = function( character, times ) {
      return new Array( times + 1 ).join( character );
    };

    if ( state === "starting" ) {
      xAxis = repChar( "/", hostAddress.length + ( yAxis.length * 2 ) );

      grunt.log.writeln( "\n\nThe FreeNAS GUI webserver service is being restarted\nIt should soon be available at this address:\n" );

      grunt.log.writeln( chalk.bgGreen( xAxis ) );
      grunt.log.writeln( chalk.bgGreen( yAxis ) + hostAddress + chalk.bgGreen( yAxis ) );
      grunt.log.writeln( chalk.bgGreen( xAxis ) );
    } else {
      xAxis = repChar( "/", failMessage.length + ( yAxis.length * 2 ) );

      grunt.log.writeln( chalk.bgRed( xAxis ) );
      grunt.log.writeln( chalk.bgRed( yAxis ) + failMessage + chalk.bgRed( yAxis ) );
      grunt.log.writeln( chalk.bgRed( xAxis ) );

      grunt.fatal( "An error occurred when trying to `start` or `restart` `/usr/sbin/service gui`" );
    }
  }

  // SSH-MULTI-EXEC COMMAND CONSTRUCTORS
  // A TestCommand will modify the testResults object with a key phrase string
  // whose boolean value is used to determine whether additional commands should
  // run next (ConditionalCommands).
  var TestCommand = function( command, testString, resultParam, passMsg, actionMsg ) {
    this.input = command;

    // If a response DOES NOT contain the test string, no action needs to be
    // taken. This is slightly counterintuitive, but necessary beacuse the null
    // or negative case is much easier to test for, in most cases (eg "Command
    // not found" vs the path of a command)

    this.success = function( data, context, done ) {
      if ( responseContains( data, testString ) ) {
        testResults[ resultParam ] = true;
        if ( typeof actionMsg === "string" && actionMsg.length ) {
          logSshMsg( actionMsg, "bold" );
        }
      } else {
        testResults[ resultParam ] = false;
        if ( typeof passMsg === "string" && passMsg.length ) {
          logSshMsg( passMsg, "green" );
        }
      }
      done();
    };
  };

  // A ConditionalCommand only runs if the key phrase provided for `shouldRun`
  // comes back as true. This makes it easy to perform a command in response to
  // the result of a TestCommand.
  var ConditionalCommand = function( shouldRun, command, didRunMsg ) {
    if ( shouldRun ) {
      this.input = command;
      if ( typeof didRunMsg === "string" && didRunMsg.length ) {
        console.log("defining!");
        this.success = function( data, context, done ) {
          logSshMsg( didRunMsg, "cyan" );
          done();
        };
      }
    } else {
      this.input = "";
    }
  };

  var SSHOptions = function() {
    this["hosts"]      = [ "<%= freeNASConfig.remoteHost %>:<%= freeNASConfig.sshPort %>" ];
    this["username"]   = "root";
    this["privateKey"] = "<%= freeNASConfig.keyPath %>";
    this["password"]   = "<%= freeNASConfig.rootPath %>";
  };

  this["enableDevMode"] = _.assign( new SSHOptions(), {
      commands : [

          { input: "rehash" }

        // Check if pkg(8) is enabled
        , new TestCommand( "cat /usr/local/etc/pkg/repos/FreeBSD.conf"
                         , "enabled: no"
                         , "pkg is not enabled"
                         , "pkg(8) is already enabled"
                         , "pkg(8) needs to be enabled" )

        // Enable pkg(8), if necessary
        , new ConditionalCommand( testResults["pkg is not enabled"]
                                , "sed -i -e 's/no/yes/' /usr/local/etc/pkg/repos/FreeBSD.conf"
                                , "Successfully enabled pkg(8)" )

        // Check if gmake is installed
        , new TestCommand( "which gmake"
                         , "Command not found"
                         , "need gmake"
                         , "gmake is installed (as " + pkgTranslations["gmake"] + ")"
                         , "gmake needs to be installed" )

        // Install gmake, if necessary
        , new ConditionalCommand( testResults["need gmake"]
                                , "env ASSUME_ALWAYS_YES=YES pkg install " + pkgTranslations["gmake"]
                                , "Successfully installed (as " + pkgTranslations["gmake"] + ")" )

        // Check if g++ (or Clang) is installed
        , new TestCommand( "which g++"
                         , "Command not found"
                         , "need g++"
                         , "g++ is installed (as " + pkgTranslations["g++"] + ")"
                         , "g++ needs to be installed" )

        // Install g++, if necessary
        , new ConditionalCommand( testResults["need g++"]
                                , "env ASSUME_ALWAYS_YES=YES pkg install " + pkgTranslations["g++"]
                                , "Successfully installed (as " + pkgTranslations["g++"] + ")" )

        // Symlink to generic term (g++)
        , new ConditionalCommand( testResults["need g++"]
                                , "ln -s /usr/local/bin/g++48 /usr/local/bin/g++"
                                , "" )

        // Sometimes your assumptions are wrong, node community.
        , new ConditionalCommand( testResults["need g++"]
                                , "ln -s /usr/local/bin/g++ /usr/local/bin/c++"
                                , "" )

        // Check if npm is installed
        , new TestCommand( "which npm"
                         , "Command not found"
                         , "need npm"
                         , "npm is installed (as " + pkgTranslations["npm"] + ")"
                         , "npm needs to be installed" )

        // Install npm, if necessary
        , new ConditionalCommand( testResults["need npm"]
                                , "env ASSUME_ALWAYS_YES=YES pkg install " + pkgTranslations["npm"]
                                , "Successfully installed (as " + pkgTranslations["npm"] + ")" )

        , { input: "rehash" }

        // Check installed version of npm (pkg is usually out of date)
        , new TestCommand( "npm -v"
                         , "1."
                         , "need to update npm"
                         , "npm is at least v2.0"
                         , "npm needs to be updated" )

        // Update npm to latest version, if necessary
        , new ConditionalCommand( testResults["need to update npm"]
                                , "npm update -g npm"
                                , "Successfully updated npm" )

        // Update path
        , { input: "rehash" }

        // Check to see if header files are found in /usr/include/
        , { input: "cd /usr/include/"
          , force: true
          , success: function( data, context, done ) {
              testResults["no header files"] = false;
              logSshMsg("Header files seem to be present in /usr/include/", "green");
              done();
            }
          , error: function( err, context, done ) {
              if ( responseContains( err, "No such" ) ) {
                testResults["no header files"] = true;
                logSshMsg("Header files will need to be copied to /usr/include/", "cyan");
                grunt.task.run("freenas-scp:header-files");
                done();
              } else {
                grunt.fail.fatal("Something went badly wrong trying to cd into /usr/include/");
                done();
              }
            }
          }

        // Make sure /usr/include exists
        , new ConditionalCommand( testResults["no header files"]
                                , "mkdir -p /usr/include/"
                                , "Created /usr/include directory (mkdir -p)" )

        // Unpack header files into /usr/include
        , new ConditionalCommand( testResults["no header files"]
                                , "tar -C /usr/include/ -xvzf /root/.tmp/headerfiles/headerfiles.tar.gz"
                                , "Header files were successfully unpacked" )

      ]
  });

  this["start-server"] = _.assign( new SSHOptions(), {
      commands: [
          { input: "cd <%= guiDirectory %> && npm install --production"
          , force: true
          , success: function( data, context, done ) {
              logSshMsg( "Finished verifying and updating npm modlues", "green" );
              done();
            }
          , error: function( error, context, done ) {
              logSshMsg( "Finished verifying and updating npm modlues, with warnings", "yellow" );
              grunt.log.writeln( error );
              done();
            }
          }
        , { input: "/usr/sbin/service gui restart"
          , success: function( data, context, done ) {
              logSshMsg( "Issuing service restart command", "cyan" );
              printServerAddress( "starting" );
              done();
            }
          , error: function( error, context, done ) {
              printServerAddress( "YOU WERE THE CHOSEN ONE" );
              done();
            }
          }
      ]
  });

  // TODO: "Stop server" might be nice

};
