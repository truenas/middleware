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


    // CREATE CONFIG FILE
    // Gather information from user about FreeNAS config
    function configInquiry() {
      var configPrompts = [
        {
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
          },
            type    : "password"
          , name    : "rootPass"
          , message : "Please enter the root password for your FreeNAS instance"
        },{
          when: function( answers ) {
            return answers["authType"] === "useKeypair";
          },
            name    : "keyPath"
          , message : "Specify path to private key file"
          , default : freenasConfig ? freenasConfig["keyPath"] : "~/.ssh/id_rsa"
        },{
            name    : "freeNASPath"
          , message : "Provide a path to a writeable volume on FreeNAS with significant free space"
          , default : freenasConfig ? freenasConfig["freeNASPath"] : null
        }
      ];

      // Run inquirer
      inquirer.prompt( configPrompts, function( answers ) {
        // Normalize provided path to have leading and trailing slashes
        var leadingSlash  = ( answers["freeNASPath"].indexOf( "/" ) === 0 );
        var trailingSlash = ( answers["freeNASPath"].indexOf( "/", answers["freeNASPath"].length - 1 ) !== -1 );
        answers["freeNASPath"] = ( ( leadingSlash ? "" : "/" ) + answers["freeNASPath"] + ( trailingSlash ? "" : "/" ) );

        // Resolve any tildes in path to key file, if provided
        if ( answers["keyPath"] && ( answers["keyPath"].indexOf("~") !== -1 ) ) {
          answers["keyPath"] = resHome( answers["keyPath"] );
        }

        // Load config file into Grunt's global variable
        grunt.config.set( ["freenasConfig"], answers );

        // Save config file to JSON
        fs.writeFile(
          grunt.config( ["configFilePath"] ),
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

    // CHECK FOR CONFIG FILE
    if ( fs.existsSync( grunt.config( ["configFilePath"] ) ) ) {

      if ( silentMode ) {
        console.log( chalk.green( "Reloading config file." ) );
      } else {
        console.log( chalk.green( "Existing FreeNAS development configuration file found." ) );
      }

      // Temporary var to cache and test JSON
      var freenasConfig = null;

      try {
        freenasConfig = JSON.parse( fs.readFileSync( grunt.config( ["configFilePath"] ), { encoding: "utf-8" } ) );
        // TODO: check typeOf for each line, make sure it looks right
      } catch ( err ) {
        // If the file wasn't parseable as JSON, delete it
        console.log( chalk.red( "Unfortunately, the config file is not formatted correctly." ) );
        console.log( chalk.red( "Deleting bad configuration file.\n" ) );
        fs.unlinkSync( grunt.config( ["configFilePath"] ) );
      }


      if ( freenasConfig ) {
        grunt.config.set( ["freenasConfig"], freenasConfig );

        if ( silentMode ) {
          asyncDone();
        } else {
          console.log( chalk.green( "Loaded configuration file." ) );
          console.log( "\nCONFIGURATION FILE:" );
          console.log( "Remote host  : " + chalk.cyan( grunt.config( ["freenasConfig"] )["remoteHost"] ) );
          console.log( "SSH port     : " + chalk.cyan( grunt.config( ["freenasConfig"] )["sshPort"] ) );
          if ( grunt.config( ["freenasConfig"] )["authType"] === "useKeypair" ) {
            console.log( "Private key  : " + chalk.cyan( grunt.config( ["freenasConfig"] )["keyPath"] ) );
          } else {
            console.log( "Password     : " + chalk.cyan( new Array( grunt.config( ["freenasConfig"] )["rootPass"].length ) ).join("*") );
          }
          console.log( "FreeNAS path : " + chalk.cyan( grunt.config( ["freenasConfig"] )["freeNASPath"] ) );
          console.log( "\n" );

          // Output a warning if the user is still using password auth
          if ( grunt.config( ["freenasConfig"] )["rootPass"] ) {
            console.log( chalk.yellow( "\nWARNING: Using password authentication will only work for configuration of the FreeNAS environment, and is not permitted for actual development.\n" ) );
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

  });
};