// BABEL
// =====
// Transpile all JSX and ES6 code into the more compatible ES5 standard.

"use strict";

module.exports = function ( grunt ) {

  this["server-side-rendering-copy"] =
    { options: { sourceMap: true }
    , files: [{ expand : true
              , cwd    : "<%= dirTree.source.jsx %>"
              , src    : [ "**/*.jsx", "**/*.js", "**/*.es6" ]
              , dest   : "<%= dirTree.build.ssrjs %>"
              , ext    : ".js"
             }]
    };
};
