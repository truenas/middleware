// DEPLOY
// Creates a deployment folder with all required dependencies for webapp. Takes
// a `--dir=xxx` option to specify a different location. Performs --production
// npm install and copies Bower components automatically.

"use strict";

var chalk = require("chalk");
var path  = require("path");

module.exports = function(grunt) {
  grunt.registerTask( "deploy", function() {
    var asyncDone  = this.async();
    var targetPath = "";

    // Use dir specified by `--dir`, if supplied
    if ( grunt.option( "dir" ) ) {
      grunt.config.set( "dirTree.deployment", grunt.option( "dir" ) );
    } else {
      console.log( chalk.yellow( "WARNING: No `--dir=` option was set. Using the default." ) );
    }

    // Set and create deployment target's path relative to current working dir
    if ( grunt.config("dirTree.deployment")[0] === "/" ) {
      targetPath = grunt.config("dirTree.deployment");
    } else {
      targetPath = path.resolve( process.cwd() + "/" + grunt.config("dirTree.deployment") );
    }
    grunt.file.mkdir( targetPath );

    console.log( chalk.cyan( "Creating FreeNAS WebGUI deployment in this directory:" ) );
    console.log( targetPath );

    grunt.task.run([
        "clean:deployment"
      , "concurrent:buildWorld"
      , "copy:deployment"
    ]);

    asyncDone();
  });
};