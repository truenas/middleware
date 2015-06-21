// CLEAN
// Removes all target directories, with subtasks for granular control.

"use strict";

module.exports = function ( grunt ) {
  this.deployment = [ "<%= dirTree.deployment %>" ];
  this.build = "<%= dirTree.build.root %>";
  this.pkgs = [ "bower_components"
              , "node_modules"
              ];
};
