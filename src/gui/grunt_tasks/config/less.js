// LESS
// Combines, processes, minifies, and uglifies LESS sourcefiles from TWBS
// and our own work, outputting our final CSS files. Again, CSS files for
// distributed code are separate to leverage caching.

"use strict";

module.exports = function ( grunt ) {
  this.core = { options: { paths: [ "<%= dirTree.source.styles %>" ] }
              , files: { "<%= dirTree.build.css %>/main.css"
                         : "<%= dirTree.source.styles %>/core.less"
                       }
              };
};
