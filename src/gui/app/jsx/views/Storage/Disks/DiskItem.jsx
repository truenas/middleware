// DISK VIEW
// =========
// Viewer overview panel for a single disk.

"use strict";

import React from "react";

const DiskItem = React.createClass(
  { render: function () {
      console.log( this.props );
      return (
        <h1>I AM A DISK YOLO</h1>
      )
    }
  }
);

export default DiskItem;
