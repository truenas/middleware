// WATCH
// Uses native filesystem methods to watch for changes in given directories,
// and executes the associated commands when a change is detected. In this
// case, it's a two-step process, where the 'bundle' created by Browserify
// is also watched in order to trigger a live reload.

"use strict";

module.exports = function( grunt ) {
  // BUILD WORLD
  // Rebuild Browserify bundle when source JS/JSX changes
  this.jsx = {
      files: ["<%= dirTree.source.jsx %>/**"]
    , tasks: [ "babel" ]
  };

  // Rebuild Browserify bundle from vanilla JS after it
  this.ssrjs = {
      files: ["<%= dirTree.build.ssrjs %>/**"]
    , tasks: [ "browserify:app" ]
  };

  // Rebuild libs.js when internal library changes
  this.internalScripts = {
      files: ["<%= dirTree.internalScripts %>/**"]
    , tasks: [ "browserify:libs" ]
  };

  // Rebuild CSS when LESS files change
  this.less = {
      files: [ "<%= dirTree.source.styles %>/**" ]
    , tasks: [ "less:core" ]
  };

  // Copy new/updated images into build
  this.images = {
      files: [ "<%= dirTree.source.images %>/**" ]
    , tasks: [ "copy:images" ]
  };


  // SERVER LIFECYCLE
  // Run local express task, restart when
  this.localServer = {
      files: [
          "<%= dirTree.routes %>.js"
        , "<%= dirTree.server %>.js"
      ]
    , tasks: [ "express:devServer" ]
  };

  // Restarts GUI service on remote FreeNAS when server or app changes
  var serverWatchFiles = [
      "<%= dirTree.server %>.js"
    , "<%= dirTree.source.templates %>/**"
    , "<%= dirTree.build.root %>/**"
    , "package.json"
    , "bower_components/**"
  ];
  this["freenasServer"] = {
      files: serverWatchFiles
    , tasks: [ "freenas-config:silent", "rsync", "ssh-multi-exec:start-server" ]
  };
};