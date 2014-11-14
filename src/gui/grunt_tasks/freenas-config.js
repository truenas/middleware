// FREENAS-CONFIG
// Loads the configuration file from JSON, if available. Prompts to create file
// if not found. Should be run as a prerequisite to any remote operations. This
// task will dequeue everything if it fails (a conf file is not found/created)

"use strict";

// Node built-ins
var fs    = require("fs");
var exec  = require("child_process").exec;

// NPM packages
var chalk     = require("chalk");
var inquirer  = require("inquirer");
var resHome   = require("expand-home-dir");

// Platform data
var currentPlatform = process.platform;
var isWindows       = ( currentPlatform === "win32" );


module.exports = function(grunt) {
  grunt.registerTask( "freenas-config", function() {
    var asyncDone  = this.async();
    // Temporary var to cache and test JSON before passing it to Grunt
    var freenasConfig  = null;

    // Silent mode should be used to reload the config file, or if you really
    // don't want to be asked about it
    var silentMode = ( this.flags["silent"] || grunt.option( "silent" ) );


    // HELPER FUNCTIONS
    // Clear queue to prevent the execution of subsequent tasks
    function noConfigExists() {
      console.log( chalk.yellow( "WARNING: A configuration file will be required before performing any remote development tasks" ) );
      grunt.task.clearQueue();

      // End state reached:
      // There is no configuration file, and the user has not created one
      asyncDone();
    }

    // SWITCH PATH BASED ON TARGET VERSION
    function getConfigPath() {
      if ( grunt.config( ["freenasVersion"] ) ) {
        switch ( grunt.config( ["freenasVersion"] ) ) {
          case 10:
            return grunt.config( ["configFilePath"] )["freenasTen"];
          case 9:
            return grunt.config( ["configFilePath"] )["freenasNine"];
          default:
            grunt.fail.fatal( "Unrecognized FreeNAS version: " + grunt.config( ["freenasVersion"] ) );
            return false;
        }
      } else {
        grunt.fail.fatal( "No FreeNAS version flag was set when getConfigPath was called" );
      }
    }

    // NO CONFIG FILE
    // Prompt the user to create a config file
    function createConfigFile() {
      var develPrompts = [
        {
            type    : "confirm"
          , name    : "createConfig"
          , message : "A FreeNAS remote configuration file was not found. Would you like to create one?"
          , default : true
        }
      ];

      inquirer.prompt( develPrompts, function( answers ) {
        if ( answers["createConfig"] ) {
          configInquiry();
        } else {
          noConfigExists();
        }
      });
    }


    // EXISTING CONFIG
    // Give user the option to skip to sshFreeNAS() if an existing config loaded
    function useExistingConfig() {
      var useExistingPrompts = [
        {
          type    : "confirm",
          name    : "useExisting",
          message : "Do you want to use this configuration file?",
          default : true
        }
      ];

      inquirer.prompt( useExistingPrompts, function( answers ) {
        if ( answers.useExisting ) {
          asyncDone();
        } else {
          configInquiry();
        }
      });
    }


    // BOTH CONFIG FILES FOUND
    // Prompt the user to delete all but one of their config files
    function chooseConfigFile() {
      var choosePrompts = [
        {
            type    : "list"
          , name    : "chooseConfig"
          , message : "Which config should be used? (All others will be deleted)"
          , choices : [ "FreeNAS 10", "FreeNAS 9" ]
          , default : 0
        }
      ];

      inquirer.prompt( choosePrompts, function( answers ) {
        if ( answers["chooseConfig"] === "FreeNAS 10" ) {
          deleteConfigFile( grunt.config( ["configFilePath"] )["freenasNine"], "Deleting unused FreeNAS 9 config file" );
        } else {
          deleteConfigFile( grunt.config( ["configFilePath"] )["freenasTen"], "Deleting unused FreeNAS 10 config file" );
        }

        // Once files have been deleted, start over
        checkAndSetConfig();
      });
    }


    // CREATE CONFIG FILE
    // Gather information from user about FreeNAS config
    function configInquiry() {
      var configPrompts = [
        {
            name     : "freenasVersion"
          , type     : "list"
          , message  : "Which version of FreeNAS are you developing on?"
          , choices  : [
              {
                  name  : "FreeNAS 10 (Recommended)"
                , value : 10
              },{
                  name  : "FreeNAS 9"
                , value : 9
              }
            ]
          , default  : 0
        },{
            name     : "remoteHost"
          , message  : "What is the IP address or hostname of your FreeNAS instance?"
          , default  : freenasConfig ? freenasConfig["remoteHost"] : null
          , validate : function(input) {
            var localDone = this.async();

            if (!input) {
              localDone("You must provide an IP address or hostname");
            } else {
              // Make sure host is reachable before continuing
              exec("ping " + ( isWindows ? "-n" : "-c" ) + " 1 " + input, function(error, stdout, stderr) {
                if (error) {
                  console.log( chalk.red.bold("ERROR: Tried to ping '" + input + "', but this happened:") );
                  console.log( chalk.red( stderr.trim() ) );
                  asyncDone();
                }
                localDone(true);
              });
            }
          }
        },{
            name    : "sshPort"
          , message : "Which port should be used for the ssh connection?"
          , default : freenasConfig ? freenasConfig["sshPort"] : 22
        },{
            name    : "authType"
          , message : "Please select the type of authorization you'd like to use for ssh and rsync"
          , type    : "list"
          , default : freenasConfig ? freenasConfig["authType"] : "useKeypair"
          , choices : [{
              name  : "I've given the root user my public key"
            , value : "useKeypair"
          },{
              name  : "Store the root password (not recommended)"
            , value : "storePass"
          }]
        },{
          when: function( answers ) {
            return answers["authType"] === "storePass";
          }
          , type    : "password"
          , name    : "rootPass"
          , message : "Please enter the root password for your FreeNAS instance"
        },{
          when: function( answers ) {
            return answers["authType"] === "useKeypair";
          }
          , name    : "keyPath"
          , message : "Specify path to private key file"
          , default : freenasConfig ? freenasConfig["keyPath"] : "~/.ssh/id_rsa"
        },{
          // FreeNAS 10 and up house the GUI in a static location
          when: function( answers ) {
            return answers["freenasVersion"] < 10;
          }
          , name    : "freeNASPath"
          , message : "Provide a path to a writeable volume on FreeNAS with significant free space"
          , default : freenasConfig ? freenasConfig["freeNASPath"] : null
        }
      ];

      // Run inquirer
      inquirer.prompt( configPrompts, function( answers ) {
        // Normalize provided path to have leading and trailing slashes
        if ( answers["freeNASPath"] ) {
          var leadingSlash  = ( answers["freeNASPath"].indexOf( "/" ) === 0 );
          var trailingSlash = ( answers["freeNASPath"].indexOf( "/", answers["freeNASPath"].length - 1 ) !== -1 );
          answers["freeNASPath"] = ( ( leadingSlash ? "" : "/" ) + answers["freeNASPath"] + ( trailingSlash ? "" : "/" ) );
        }

        // Resolve any tildes in path to key file, if provided
        if ( answers["keyPath"] && ( answers["keyPath"].indexOf("~") !== -1 ) ) {
          answers["keyPath"] = resHome( answers["keyPath"] );
        }

        // Shim path into answers object for modern FreeNAS
        if ( !answers["freeNASPath"] ) {
          answers["freeNASPath"] = "/usr/local/www/gui";
        }

        // Load version flag and config file into Grunt's globals
        grunt.config.set( ["freenasConfig"], answers );
        grunt.config.set( ["freenasVersion"], answers["freenasVersion"] );

        // Save config file to JSON
        fs.writeFile(
          getConfigPath(),
          JSON.stringify( grunt.config( ["freenasConfig"] ), null, 2 ),
          function( err ) {
            if ( err ) {
              grunt.fail.fatal( chalk.red( "ERROR: Could not save configuration file\n" ) );
              grunt.task.clearQueue();
              // Can't continue
              asyncDone();
            } else {
              console.log( chalk.green("\nFreeNAS development configuration saved successfully.\n") );
              // A config file has been loaded into Grunt and saved as JSON
              asyncDone();
            }
          });
      });
    }


    // DELETE CONFIG FILE
    // Deletes a configuration file, provided a path and optional message
    function deleteConfigFile( targetPath, deleteMsg ) {
      if ( deleteMsg ) {
        console.log( chalk.red( deleteMsg ) );
      }
      fs.unlinkSync( targetPath );
    }


    // CHECK AND SET CONFIG FILE
    function checkAndSetConfig() {
      // Determine which config file(s) are present
      var existsNine = fs.existsSync( grunt.config( ["configFilePath"] )["freenasNine"] );
      var existsTen  = fs.existsSync( grunt.config( ["configFilePath"] )["freenasTen"] );

      if ( existsTen && existsNine ) {
        // Somehow, the user has both config files
        console.log( chalk.yellow( "Detected both a FreeNAS 9 and a FreeNAS 10 config file. You can only keep one." ) );
        chooseConfigFile();
      } else if ( existsTen || existsNine ) {
        // Set version flag
        grunt.config.set( ["freenasVersion"], ( existsTen ? 10 : 9 ) );

        if ( silentMode ) {
          console.log( chalk.green( "Reloading config file." ) );
        } else {
          console.log( chalk.green( "Existing FreeNAS " + grunt.config( ["freenasVersion"] ) + " development configuration file found." ) );
        }

        try {
          freenasConfig = JSON.parse( fs.readFileSync( getConfigPath(), { encoding: "utf-8" } ) );
          // TODO: check typeOf for each line, make sure it looks right
        } catch ( err ) {
          // If the file wasn't parseable as JSON, delete it
          console.log( chalk.red( "Unfortunately, the config file is not formatted correctly." ) );
          deleteConfigFile( getConfigPath(), "Deleting bad configuration file.\n" );
        }

        if ( freenasConfig ) {
          grunt.config.set( ["freenasConfig"], freenasConfig );

          if ( silentMode ) {
            if ( grunt.config( ["freenasConfig"] )["rootPass"] ) {
              grunt.fail.warn( "Use of password authentication for live development is forbidden. Please create a new config file." );
            } else {
              asyncDone();
            }
          } else {
            console.log( chalk.green( "Loaded FreeNAS" + grunt.config( ["freenasVersion"] ) + " configuration file." ) );
            console.log( "\nFREENAS " + grunt.config( ["freenasVersion"] ) + " CONFIGURATION FILE:" );
            console.log( "Remote host  : " + chalk.cyan( grunt.config( ["freenasConfig"] )["remoteHost"] ) );
            console.log( "SSH port     : " + chalk.cyan( grunt.config( ["freenasConfig"] )["sshPort"] ) );
            if ( grunt.config( ["freenasConfig"] )["authType"] === "useKeypair" ) {
              console.log( "Private key  : " + chalk.cyan( grunt.config( ["freenasConfig"] )["keyPath"] ) );
            } else {
              console.log( "Password     : " + chalk.cyan( new Array( grunt.config( ["freenasConfig"] )["rootPass"].length ) ).join("*") );
            }
            if ( grunt.config( ["freenasVersion"] ) < 10 ) {
              console.log( "FreeNAS path : " + chalk.cyan( grunt.config( ["freenasConfig"] )["freeNASPath"] ) );
            }
            console.log( "\n" );

            // Output a warning if the user is still using password auth
            if ( grunt.config( ["freenasConfig"] )["rootPass"] ) {
              console.log( chalk.yellow( "\nNOTE: Using password authentication will only work for configuration of the FreeNAS environment, and is not permitted for actual development.\n" ) );
            }

            // Config was found and validated. Ask the user if they want to use it
            useExistingConfig();
          }
        } else {
          // Config was found, but invalid. Ask the user to create a config.
          createConfigFile();
        }
      } else {
        // No config file exists. Ask the user to create a config.
        createConfigFile();
      }
    }


    // START
    checkAndSetConfig();
  });
};