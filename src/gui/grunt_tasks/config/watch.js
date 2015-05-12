// WATCH
// Uses native filesystem methods to watch for changes in given directories,
// and executes the associated commands when a change is detected. In this
// case, it's a two-step process, where the 'bundle' created by Browserify
// is also watched in order to trigger a live reload.

"use strict";

module.exports = function ( grunt ) {

  var serverTasks = [ "freenas-config:silent"
                    , "rsync"
                    , "ssh-multi-exec:start-server"
                    ]

  // BUILD WORLD
  // Rebuild Browserify bundle when source JS/JSX changes
  this.jsx = { files: [ "<%= dirTree.source.jsx %>/**" ]
             , tasks: [ "jscs:check-javascript-quality"
                      , "babel"
                      , "browserify:app"
                      ].concat( serverTasks )
             };

  // Rebuild libs.js when internal library changes
  this.internalScripts = { files: [ "<%= dirTree.internalScripts %>/**" ]
                         , tasks: [ "browserify:libs" ].concat( serverTasks )
                         };

  // Rebuild CSS when LESS files change
  this.less = { files: [ "<%= dirTree.source.styles %>/**" ]
              , tasks: [ "less:core" ].concat( serverTasks )
              };

  // Copy new/updated images into build
  this.images = { files: [ "<%= dirTree.source.images %>/**" ]
                , tasks: [ "copy:images" ].concat( serverTasks )
                };


  // SERVER LIFECYCLE
  // Restarts GUI service on remote FreeNAS when server or app changes
  this["freenasServer"] = { files: [ "<%= dirTree.server %>.js"
                                   , "<%= dirTree.source.templates %>/**"
                                   , "package.json"
                                   , "bower_components/**"
                                   ]
                          , tasks: serverTasks
                          };
};
