"use strict";

// RELOAD
// Delete npm and Bower packages and reload all
module.exports = function ( grunt ) {
  grunt.registerTask( "reload", function () {
    var reloadTasks = [ "shell:reloadPackages" ];

    if ( grunt.option( "local-only" ) ) {
      reloadTasks.unshift( "clean:local" );
    } else {
      reloadTasks.unshift( "clean" );
    }
    grunt.task.run( reloadTasks );
  });
};
