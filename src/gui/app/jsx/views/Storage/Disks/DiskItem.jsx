// DISK VIEW
// =========
// Viewer overview panel for a single disk.

"use strict";

import React from "react";

import ByteCalc from "../../../common/ByteCalc";

const DiskItem = React.createClass(
  { getInitialState: function () {
      return {
        byteValue: ""
      };
    }

  , handleByteChange: function ( event ) {
      this.setState({
        byteValue: event.target.value
      });
    }

  , render: function () {
      return (
        <div>
          <input onChange = { this.handleByteChange } />
          <h1>{ ByteCalc.humanize( this.state.byteValue ) }</h1>
        </div>
      )
    }
  }
);

export default DiskItem;
