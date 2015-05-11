// CHECK-DEV-ENV
// A sanity check for the local development environment. Run as a prerequisite
// to all development, local or remote.

"use strict";

// Node Built-ins
var exec  = require( "child_process" ).exec;

// NPM packages
var chalk = require( "chalk" );

module.exports = function ( grunt ) {
  grunt.registerTask( "check-dev-env", function () {
    var asyncDone = this.async();

    if ( grunt.option( "skip-check" ) ) {
      console.log(
        chalk.yellow( "WARNING: Skipping environment check. I hope you know " +
                      "what you're doing." )
      );
      asyncDone();
    }

    // Platform data
    var currentPlatform = process.platform;
    var isWindows       = ( currentPlatform === "win32" );
    var testedPlatforms =
      { full: { freebsd : "FreeBSD"
              , darwin  : "Mac OSX"
              }
      , partial: { linux : "Linux"
                 , win32 : "Windows"
                 }
      };

    var required  = [ "ping", "ssh", "rsync", "tar", "scp" ];
    var found = { installed: [], missing: [] };

    // Use 'which' to detect local tools
    function isInstalled ( command, callback ) {
      exec( "which " + command, function ( error, stdout, stderr ) {
        if ( error ) {
          console.log(
            chalk.red( "\nERROR: Your system doesn't have " + command +
                       " installed" )
          );
          callback( command, "missing" );
        } else {
          callback( command, "installed" );
        }
      });
    }

    // Syncronously check if software is installed, and return status to hash
    required.map( function ( software ) {
      isInstalled( software, function ( software, status ) {
        found[status].push( software );
        // The last item in 'required' will trigger the final check
        if ( required.length === found.installed.length +
                                 found.missing.length ) {
          checkRequired();
        }
      });
    });

    function checkRequired () {
      if ( testedPlatforms.full[currentPlatform] ) {
        console.log(
          chalk.green( testedPlatforms.full[currentPlatform] +
                       " is a supported development environment." ) );
      } else if ( testedPlatforms.partial[currentPlatform] ) {
        console.log(
          chalk.yellow( testedPlatforms.partial[currentPlatform] +
                        " is only partially supported as a development " +
                        "environment, and may not have been fully tested. " +
                        "Proceed with caution." )
        );
      } else {
        console.log(
          chalk.red( currentPlatform + " has not been tested as a " +
                     "development environment. It may not work as expected." )
        );
      }

      if ( !found.missing.length ) {
        console.log(
          chalk.green.bold( "Development environment has all required " +
                            "software.\n" )
        );
        asyncDone();
      } else {
        if ( isWindows ) {
          console.log(
            "Windows users will need to do the following:\n" +
            " - Install Cygwin\n" +
            " - Install Cygwin modules for:\n" +
            "   - openssh\n" +
            "   - rsync\n" +
            " - Add C:\\cygwin\\bin to Windows PATH"
          );
          console.log(
            chalk.red( "Cannot proceed with automatic configuration\n" )
          );
        }
        // Clear queue to prevent the execution of subsequent tasks
        grunt.task.clearQueue();
        asyncDone();
      }
    }
  });
};