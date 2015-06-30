// POOL/VOLUME DATASETS
// ====================
// A section of the Pool/Volume UI that shows the available storage devices,
// datasets, ZVOLs, etc.

"use strict";

import React from "react";
import TWBS from "react-bootstrap";

var PoolDatasets = React.createClass({

  render: function () {
    return (
      <TWBS.Well
        style = {{ display: "none" }}
      >
        <h1>Storage goes here, when you have it</h1>
      </TWBS.Well>
    );
  }

});

export default PoolDatasets;
