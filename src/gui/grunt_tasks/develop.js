// DEVELOP
// Meta task for managing local and remote development. Constructs task queues
// on the fly, and prompts users to enter any required information or install
// any required software.

"use strict";

module.exports = function ( grunt ) {
  grunt.registerTask( "develop", function () {
    var asyncDone = this.async();

    // Run `npm install`
    grunt.log.ok( "Installing npm packages" );
    grunt.task.run( "npm-install" );

    // Run `bower install`
    grunt.log.ok( "Installing bower components" );
    grunt.task.run( "bower:install" );

    // Sanity check development environment before proceeding
    grunt.task.run( "check-dev-env" );

    // Clean the build directory
    grunt.task.run( "clean:build" );

    // Check the code quality
    grunt.log.ok( "Checking JavaScript code quality" );
    grunt.task.run( "jscs:check-javascript-quality" );

    // Compile app source into usable formats
    grunt.task.run( "concurrent:buildWorld" );

    // Create the browserify bundle
    grunt.task.run( "browserify" );

    // Check for a configuration file before proceeding
    grunt.task.run( "freenas-config" );

    // Begin live development
    grunt.task.run( "begin-livedev" );

    asyncDone();
  });
};
