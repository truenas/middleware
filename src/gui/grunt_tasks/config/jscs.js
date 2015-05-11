// JSCS
// ====
// Code linting, syntax correcting, and style guide enforcement. Your tears
// sustain me.

"use strict";

module.exports = function ( grunt ) {

  this["check-javascript-quality"] =
    { options: { force          : true
               , config         : "<%= dirTree.root %>/../../.jscsrc"
               , esnext         : true
               , verbose        : true
               , reporterOutput : "<%= dirTree.root %>/../../grunt-jscs.log"
               }
    , files: [{ expand : true
              , cwd    : "<%= dirTree.source.jsx %>"
              , src    : [ "**/*.jsx", "**/*.js", "**/*.es6" ]
              , dest   : "<%= dirTree.build.ssrjs %>"
              , ext    : ".js"
             }]
    };
};
