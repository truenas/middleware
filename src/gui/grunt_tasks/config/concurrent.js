// CONCURRENT
// This allows Grunt to maintain several tasks at the same time. It's useful
// in conjunction with watch, and also for performing non-blocking build
// operations concurrently.

"use strict";

module.exports = function ( grunt ) {

  var serverCommon = [ "watch:jsx"
                     , "watch:less"
                     , "watch:images"
                     , "watch:internalScripts"
                     ];

  this.options = { logConcurrentOutput : true
                 , limit : 8 // Hope you have a quad i7!
                 };

  // Run `npm install`
  // Run `bower install`
  // Sanity check development environment before proceeding
  // Clean the build directory
  // Check the code quality
  this.initDevelop = [ "npm-install"
                     , "bower:install"
                     , "check-dev-env"
                     , "clean:build"
                     , "jscs:check-javascript-quality"
                     ];

  // Initial build of app
  this.buildWorld = [ "copy:images"
                    , "copy:favicons"
                    , "copy:openSans"
                    , "copy:fontawesome"
                    , "less"
                    ];

  this["watchLocalServer"]   = serverCommon.concat( "watch:localServer" );
  this["watchRemoteFreeNAS"] = serverCommon.concat( "watch:freenasServer" );
};
