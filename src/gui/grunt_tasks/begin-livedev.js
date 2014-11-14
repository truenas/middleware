// BEGIN-LIVEDEV
// Meta task for beginning live development tasks, switched by target FreeNAS
// version.

"use strict";

var chalk = require("chalk");

module.exports = function(grunt) {
  grunt.registerTask( "begin-livedev", function() {
    console.log( chalk.green( "Beginning live development session for FreeNAS " + grunt.config( ["freenasVersion"] ) ) );
    if ( grunt.config( ["freenasVersion"] ) === 10 ) {
      // Sanity check remote environment
      grunt.task.run( "freenas-server:bootstrap" );

      // rsync initial payload
      grunt.task.run( "rsync" );

      // Start remote server once app has been built
      grunt.task.run( "freenas-server:start" );

      // Run concurrent watch operations for remote development
      grunt.task.run( "concurrent:watchRemoteFreeNAS" );
    } else {
      // Sanity check remote environment
      grunt.task.run( "freenas-server:bootstrap-legacy" );

      // rsync initial payload
      grunt.task.run( "rsync" );

      // Start remote server once app has been built
      grunt.task.run( "freenas-server:start-legacy" );

      // Run concurrent watch operations for remote development
      grunt.task.run( "concurrent:watchRemoteFreeNAS-legacy" );
    }
  });
};