// DISKS VIEW
// ==========
// Overview of all the hard disks in your FreeNAS system.

"use strict";

import React from "react";

import ByteCalc from "../../common/ByteCalc";
import Viewer from "../../components/Viewer";

import DS from "../../stores/DisksStore";
import DM from "../../middleware/DisksMiddleware";

function getDisksFromStore () {
  return { disks: DS.getAllDisks() };
}

const Disks = React.createClass(

  { getInitialState: function () {
      return { inputValue : ""
             , disks      : getDisksFromStore()
             };
    }

  , componentDidMount: function () {
      DS.addChangeListener( this.handleDisksChange );
      DM.requestDisksOverview();
      DM.subscribe( this.constructor.displayName );
    }

  , componentWillUnmount: function () {
      DS.removeChangeListener( this.handleDisksChange );
      DM.unsubscribe( this.constructor.displayName );
    }

  , handleDisksChange: function () {
      this.setState( getDisksFromStore() );
    }

  , handleInputChange: function ( event ) {
      this.setState({ inputValue: event.target.value })
    }

  , render: function () {
      let output = ByteCalc.convertString( this.state.inputValue );

      return (
        <div>
          <input onChange = { this.handleInputChange }
                 value    = { this.state.inputValue } />
          <h1>{ ByteCalc.humanize( output, false, true ) }</h1>
        </div>
      );
    }

  }

);

export default Disks;
