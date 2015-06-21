// VIEWER MODE MIXIN
// =================
// This mixin performs the same function as a "viewer mode" baseclass would.
// Once ES6 classes are viable in React, this can be refactored to an actual
// base class. For the time being, it shoulc contain common propTypes,
// contextTypes, and methods that each of the viewer modes rely on.

"use strict";

import React from "react";

const ViewerMode =

  { propTypes:
    { handleItemSelect : React.PropTypes.func.isRequired

    , filteredData     : React.PropTypes.object.isRequired
    , selectedItem     : React.PropTypes.oneOfType(
                           [ React.PropTypes.number
                           , React.PropTypes.string
                           ]
                         )
    }

    , searchString : React.PropTypes.string.isRequired
    , filteredData : React.PropTypes.object.isRequired
    , columnsEnabled : React.PropTypes.instanceOf( Set ).isRequired
  };

export default ViewerMode;
