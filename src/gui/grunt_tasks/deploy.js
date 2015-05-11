// DEPLOY
// Creates a deployment folder with all required dependencies for webapp. Takes
// a `--dir=xxx` option to specify a different location. Performs --production
// npm install and copies Bower components automatically.

"use strict";

var chalk = require( "chalk" );
var path  = require( "path" );

module.exports = function ( grunt ) {
  var targetPath = "";

  // Set and create deployment target's path relative to current working dir
  var setTarget = function ( inputPath ) {
    if ( inputPath[0] === "/" ) {
      targetPath = inputPath;
    } else {
      targetPath = path.resolve( process.cwd() + "/" + inputPath );
    }
  };

  grunt.registerTask( "deploy", function () {
    var asyncDone  = this.async();

    // Use dir specified by `--dir`, if supplied
    if ( grunt.option( "dir" ) ) {
      grunt.config.set( "dirTree.deployment", grunt.option( "dir" ) );
    } else {
      console.log(
        chalk.yellow( "WARNING: No `--dir=` option was set. Using the " +
                      "default." )
      );
    }

    setTarget( grunt.config( "dirTree.deployment" ) );
    grunt.file.mkdir( targetPath );

    console.log(
      chalk.cyan( "Creating FreeNAS WebGUI deployment in this directory:" )
    );
    console.log( targetPath );

    grunt.task.run(
      [ "clean:deployment"
      , "jscs:check-javascript-quality"
      , "concurrent:buildWorld"
      , "browserify"
      , "copy:deployment"
      , "deploy-npm"
      ]
    );

    asyncDone();
  });

  grunt.registerTask( "deploy-npm", function () {
    // Don't run unless the copy task has already been run
    grunt.task.requires( "copy:deployment" );

    if ( process.platform !== "freebsd" ) {
      grunt.fail.warn( "Production deployments must be done on FreeBSD only." );
    }

    process.chdir( targetPath );
    grunt.task.run( "shell:npmProduction" );
  });
};
