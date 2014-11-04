// COPY
// Straight copy of static sourcefiles into the build dir. This is used for
// images that don't need processing, libs which are precompiled, and other
// purely static assets.

"use strict";

module.exports = function( grunt ) {
  this.favicons = {
    files: [{
        src     : "<%= dirTree.source.favicons %>/**"
      , dest    : "<%= dirTree.build.root %>"
      , filter  : "isFile"
      , expand  : true
      , flatten : true
    }]
  };

  this.images = {
    files: [{
        src     : "<%= dirTree.source.images %>/**"
      , dest    : "<%= dirTree.build.img %>"
      , filter  : "isFile"
      , expand  : true
      , flatten : true
    }]
  };

  this.deployment = {
    files: [{
        src: [
            "<%= dirTree.build.root %>/**"
          , "bower_components/**"
          , "package.json"
        ]
      , dest    : "<%= dirTree.deployment %>"
      , expand  : true
    }]
  };
};