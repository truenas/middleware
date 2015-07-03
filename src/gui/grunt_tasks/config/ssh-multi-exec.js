// SSH-MULTI-EXEC
// Allows the execution of remote SSH commands based on input credentials.

"use strict";

var _          = require( "lodash" );
var chalk      = require( "chalk" );
var SshHelpers = require( "../common/ssh-helpers" );

module.exports = function ( grunt ) {

  var conditionalCommands = {};
  var actionsNeeded       = [];

  var ssh = new SshHelpers( grunt );


  // SSH-MULTI-EXEC COMMAND CONSTRUCTORS

  var SSHOptions = function () {
    this["hosts"]      = [ "<%= freeNASConfig.remoteHost %>" + ":" +
                           "<%= freeNASConfig.sshPort %>" ];
    this["username"]   = "root";
    this["privateKey"] = "<%= freeNASConfig.keyPath %>";
    this["password"]   = "<%= freeNASConfig.rootPath %>";
  };

  this["verify-development-environment"] = _.assign( new SSHOptions(), {
    commands :
      [ { input: "rehash" }

      // Check if pkg(8) is enabled
      , { input: "cat /usr/local/etc/pkg/repos/FreeBSD.conf"
        , success: function ( data, context, done ) {
            if ( ssh.responseContains( data, "enabled: no" ) ) {
              actionsNeeded.push( "pkg(8) needs to be enabled" );

              conditionalCommands["enablePkg"] =
                "sed -i -e 's/no/yes/' /usr/local/etc/pkg/repos/FreeBSD.conf";
            }
            done();
          }
        }

      // Check if gmake is installed
      , { input: "which gmake"
        , success: function ( data, context, done ) {
            if ( ssh.responseContains( data, "Command not found" ) ) {
              actionsNeeded.push( "gmake needs to be installed" );

              conditionalCommands["installGmake"] =
                "env ASSUME_ALWAYS_YES=YES pkg install gmake";
            }
            done();
          }
        }

      // Check if g++ (or Clang) is installed
      , { input: "which g++"
          , success: function ( data, context, done ) {

            if ( ssh.responseContains( data, "Command not found" ) ) {
              actionsNeeded.push( "g++ needs to be installed" );

              conditionalCommands["installGplusplus"] =
                "env ASSUME_ALWAYS_YES=YES pkg install g++";

              conditionalCommands["symlinkGplusplus"] =
                "ln -s /usr/local/bin/g++48 /usr/local/bin/g++";

              conditionalCommands["symlinkCplusplus"] =
                "ln -s /usr/local/bin/g++ /usr/local/bin/c++";
            }

            done();
          }
        }

      // Check if npm is installed
      , { input: "which npm"
          , success: function ( data, context, done ) {

            if ( ssh.responseContains( data, "Command not found" ) ) {
              actionsNeeded.push( "npm needs to be installed" );

              conditionalCommands["installNpm"] =
                "env ASSUME_ALWAYS_YES=YES pkg install npm";

              conditionalCommands["updateNpm"] = "npm update -g npm";
            }

            done();
          }
        }

      // Perform any conditional tasks that must be performed
      , { input: "rehash"
            , success: function ( data, context, done ) {
              if ( actionsNeeded.length ) {
                grunt.log.writeln(
                  chalk.bold( "The following issues will need to be " +
                              " corrected:" )
                );
                grunt.log.writeln(
                  chalk.cyan( " * " + actionsNeeded.join( "\n * " ) )
                );

                grunt.config.set( [ "conditionalCommands" ]
                                , conditionalCommands );

                grunt.task.run(
                  "ssh-multi-exec:modify-development-environment"
                );
              }

              done();
            }
          }
        ]
  });

  this["modify-development-environment"] = _.assign( new SSHOptions(), {
    commands : [
      // Enable pkg(8), if necessary
        { input: "<%= conditionalCommands.enablePkg %>" }

      // Install gmake, if necessary
      , { input: "<%= conditionalCommands.installGmake %>"
        , force: true
        }

      // Install g++, if necessary
      , { input: "<%= conditionalCommands.installGplusplus %>"
        , force: true
        }

      // Symlink to generic term (g++)
      , { input: "<%= conditionalCommands.symlinkGplusplus %>"
        , force: true
        }

      // Sometimes your assumptions are wrong, node community.
      , { input: "<%= conditionalCommands.symlinkCplusplus %>"
        , force: true
        }

      // Install npm, if necessary
      , { input: "<%= conditionalCommands.installNpm %>"
        , force: true
        }

      , { input: "rehash" }

      // Update npm to latest version, if necessary
      , { input: "<%= conditionalCommands.updateNpm %>"
        , force: true
        }

      , { input: "rehash" }
    ]
  });

  this["start-server"] = _.assign( new SSHOptions(), {
    commands: [
        { input: "cd <%= guiDirectory %> && npm install --production"
        , force: true
          , success: function ( data, context, done ) {
              ssh.logSshMsg( "Finished verifying and updating npm modlues"
                       , "green"
                       );
              done();
            }
          , error: function ( error, context, done ) {
              ssh.logSshMsg( "Finished verifying and updating npm modlues, with " +
                         "warnings"
                       , "yellow"
                       );
              grunt.log.writeln( error );
              done();
            }
          }
        , { input: "/bin/launchctl stop org.freenas.gui " +
                   "&& sleep 3 && /bin/launchctl start org.freenas.gui"
          , success: function ( data, context, done ) {
              ssh.logSshMsg( "Issuing service restart command", "cyan" );
              ssh.printServerAddress( "starting" );
              done();
            }
          , error: function ( error, context, done ) {
              ssh.printServerAddress( "YOU WERE THE CHOSEN ONE" );
              done();
            }
          }
      ]
  });

  // TODO: "Stop server" might be nice

};
