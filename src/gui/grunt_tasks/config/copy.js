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

  this.openSans = {
    files: [{
      src: [
          // LIGHT
          "<%= dirTree.bower.openSans.fonts %>/OpenSans-Light/**"
        , "<%= dirTree.bower.openSans.fonts %>/OpenSans-LightItalic/**"
          // REGULAR
        , "<%= dirTree.bower.openSans.fonts %>/OpenSans-Italic/**"
        , "<%= dirTree.bower.openSans.fonts %>/OpenSans-Regular/**"
          // SEMIBOLD
        , "<%= dirTree.bower.openSans.fonts %>/OpenSans-Semibold/**"
        , "<%= dirTree.bower.openSans.fonts %>/OpenSans-SemiboldItalic/**"
          // BOLD
        , "<%= dirTree.bower.openSans.fonts %>/OpenSans-Bold/**"
        , "<%= dirTree.bower.openSans.fonts %>/OpenSans-BoldItalic/**"
          // EXTRABOLD
        , "<%= dirTree.bower.openSans.fonts %>/OpenSans-ExtraBold/**"
        , "<%= dirTree.bower.openSans.fonts %>/OpenSans-ExtraBoldItalic/**"
      ]
      , dest    : "<%= dirTree.build.font %>"
      , filter  : "isFile"
      , expand  : true
      , flatten : true
    }]
  };

  this.deployment = {
    files: [{
        src: [
            "<%= dirTree.build.root %>/**"
          , "<%= dirTree.source.jsx %>/**"
          , "<%= dirTree.source.templates %>/**"
          , "<%= dirTree.client %>.js"
          , "<%= dirTree.server %>.js"
          , "<%= dirTree.routes %>.js"
          , "<%= dirTree.data %>/**"
          , "bower_components/**"
          , "package.json"
        ]
      , dest    : "<%= dirTree.deployment %>"
      , expand  : true
    }]
  };
};