// CONCURRENT
// This allows Grunt to maintain several tasks at the same time. It's useful
// in conjunction with watch, and also for performing non-blocking build
// operations concurrently.

"use strict";

module.exports = function ( grunt ) {

  var serverCommon = [ "watch:jsx"
                     , "watch:less"
                     , "watch:images"
                     ];

  this.options = { logConcurrentOutput : true
                 , limit : 6
                 };

  // Initial build of app
  this.buildWorld = [ "babel"
                    , "copy:images"
                    , "copy:favicons"
                    , "copy:openSans"
                    , "copy:fontawesome"
                    , "less"
                    ];

  this["watchRemoteFreeNAS"] = serverCommon.concat( "watch:freenasServer" );
};
