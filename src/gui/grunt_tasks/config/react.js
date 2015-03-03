// REACT
//

"use strict";

module.exports = function( grunt ) {

  this["server-side-rendering-copy"] = {
    files: [
      {
          expand : true
        , cwd    : "<%= dirTree.source.jsx %>"
        , src    : [ "**/*.jsx", "**/*.js" ]
        , dest   : "<%= dirTree.build.ssrjs %>"
        , ext    : ".js"
      }
    ]
  };

};
