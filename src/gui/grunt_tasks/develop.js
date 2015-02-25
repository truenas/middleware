// DEVELOP
// Meta task for managing local and remote development. Constructs task queues
// on the fly, and prompts users to enter any required information or install
// any required software.

"use strict";

module.exports = function(grunt) {
  grunt.registerTask( "develop", function() {
    var asyncDone = this.async();

    // Sanity check development environment before proceeding
    grunt.task.run( "check-dev-env" );

    // Clean the build directory
    grunt.task.run( "clean:build" );

    // Build the app
    grunt.task.run( "concurrent:buildWorld" );


    // Development is remote by default
    if ( grunt.option( "local" ) ) {
      // Run concurrent watch operations for local development
      grunt.task.run( "concurrent:watchLocalServer" );
    } else {
      // Check for a configuration file before proceeding
      grunt.task.run( "freenas-config" );

      // Begin live development
      grunt.task.run( "begin-livedev" );
    }
    asyncDone();
  });
};
