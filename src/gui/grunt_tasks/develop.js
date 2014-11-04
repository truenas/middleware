// DEVELOP
// Meta task for managing local and remote development. Constructs task queues
// on the fly, and prompts users to enter any required information or install
// any required software.

"use strict";

var chalk = require("chalk");

module.exports = function(grunt) {
  grunt.registerTask( "develop", function() {
    var asyncDone = this.async();

    // Sanity check development environment before proceeding
    if ( grunt.option( "insane" ) ) {
      console.log( chalk.yellow( "INSANE: Not checking dev environment. Full speed ahead!" ) );
    } else {
      grunt.task.run( "check-dev-env" );
    }

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

      // Sanity check remote environment
      if ( grunt.option( "insane" ) ) {
        console.log( chalk.yellow( "INSANE: Not checking FreeNAS readiness. Just keep going!" ) );
      } else {
        grunt.task.run( "freenas-server:bootstrap" );
      }

      // rsync initial payload
      grunt.task.run( "rsync" );

      // Start remote server once app has been built
      grunt.task.run( "freenas-server:start" );

      // Run concurrent watch operations for remote development
      grunt.task.run( "concurrent:watchRemoteFreeNAS" );
    }
    asyncDone();
  });
};