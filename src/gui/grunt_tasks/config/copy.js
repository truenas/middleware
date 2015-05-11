// COPY
// Straight copy of static sourcefiles into the build dir. This is used for
// images that don't need processing, libs which are precompiled, and other
// purely static assets.

"use strict";

module.exports = function( grunt ) {
  this.favicons = { files: [
                      { src     : "<%= dirTree.source.favicons %>/**"
                      , dest    : "<%= dirTree.build.root %>"
                      , filter  : "isFile"
                      , expand  : true
                      , flatten : true
                      }
                    ]
                  };

  this.images =
    { files: [
        { src     : "<%= dirTree.source.images %>/**"
        , dest    : "<%= dirTree.build.img %>"
        , filter  : "isFile"
        , expand  : true
        , flatten : true
        }
      ]
    };

  this.openSans =
    { files: [
        { src:
          [ "<%= dirTree.bower.openSans.fonts %>/OpenSans-Light/**"
            // LIGHT
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
        }
      ]
    };

  // NOTE: FontAwesome is NOT A PERMANENT ADDITION. It's going to be removed.
  // Don't get used to it, don't decide you like it, don't convince others of its
  // merits. FreeNAS is going to roll its OWN icon font to match our own visual
  // style. This should be considered extremely temporary.
  this.fontawesome = { files: [
                         { src     : "<%= dirTree.bower.fontawesome.fonts %>/**"
                         , dest    : "<%= dirTree.build.font %>"
                         , filter  : "isFile"
                         , expand  : true
                         , flatten : true
                         }
                       ]
                     };

  this.deployment = { files: [
                      { src: [ "<%= dirTree.build.root %>/**"
                             , "<%= dirTree.source.jsx %>/**"
                             , "<%= dirTree.source.templates %>/**"
                             , "<%= dirTree.server %>.js"
                             , "<%= dirTree.build.ssrjs %>/**"
                             , "<%= dirTree.data %>/**"
                             , "bower_components/**"
                             , "package.json"
                             ]
                      , dest    : "<%= dirTree.deployment %>"
                      , expand  : true
                      }
                    ]
                  };

};
