// BROWSERIFY
// Browserify concatenates JS source files into a single 'bundle'. This
// not only reduces requests on initial load, but ensures that the first
// payload gets all of the application code, and prevents subsequent loads.
// It's also being used here to package some libs (which won't change often)
// and the appcode (which will) to leverage browser caching.

"use strict";

module.exports = function ( grunt ) {

  // WEBAPP
  this.app = { src  : [ "<%= dirTree.build.ssrjs %>/client.js" ]
             , dest : "<%= dirTree.build.app %>/app.js"
             };

  // EXTERNAL LIBRARIES
  this.libs = { src: [ "<%= dirTree.bower.velocity %>/velocity.min.js"
                     , "<%= dirTree.bower.velocity %>/velocity.ui.min.js"
                     , "<%= dirTree.bower.d3 %>/d3.js"
                     , "<%= dirTree.babel %>/browser-pollyfill.min.js"
                     , "<%= dirTree.internalScripts %>/nv.d3.js"
                     ]
              , dest : "<%= dirTree.build.dist %>/libs.js"
              };
};
