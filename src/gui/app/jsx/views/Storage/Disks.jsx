// DISKS VIEW
// ==========
// Overview of all the hard disks in your FreeNAS system.

"use strict";

import React from "react";

import ByteCalc from "../../common/ByteCalc";
import Viewer from "../../components/Viewer";

import DisksStore from "../../stores/DisksStore";
// import DisksMiddleware from "../../middleware/DisksMiddleware";

const Disks = React.createClass(

  { getInitialState: function () {
      return { inputValue: "" };
    }

  , componentDidMount: function () {
      window.ByteCalc = ByteCalc;
    }

  , handleInputChange: function ( event ) {
      this.setState({ inputValue: event.target.value })
    }

  , render: function () {
      let output = ByteCalc.convertString( this.state.inputValue );

      return (
        <div>
          <input onChange={ this.handleInputChange } value={ this.state.inputValue } />
          <h1>{ ByteCalc.humanize( output, false, true ) }</h1>
        </div>
      );
    }

  }

);

export default Disks;
