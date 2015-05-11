// BEGIN-LIVEDEV
// Meta task for beginning live development tasks, switched by target FreeNAS
// version.

"use strict";

var chalk = require( "chalk" );

module.exports = function ( grunt ) {

  grunt.registerTask( "begin-livedev", function () {
    grunt.log.writeln(
      chalk.green( "Beginning live development session for FreeNAS 10" )
    );

    // Sanity check remote environment
    grunt.task.run( "ssh-multi-exec:verify-development-environment" );

    // Rsync initial payload
    grunt.task.run( "rsync" );

    // Start remote server once app has been built
    grunt.task.run( "ssh-multi-exec:start-server" );

    // Run concurrent watch operations for remote development
    grunt.task.run( "concurrent:watchRemoteFreeNAS" );
  });

};
