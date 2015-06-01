

"use strict";

import React from "react";

import Widget from "../Widget";

import SystemMiddleware from "../../middleware/SystemMiddleware";
import SystemStore from "../../stores/SystemStore";

import UpdateStore from "../../stores/UpdateStore";

import round from "round";

var SystemInfo = React.createClass({

  getInitialState: function () {
    return {
      hardware   :   ""
      , version    :   ""
      , updates    :   ""
      , train      :   ""
    };
  }

  , componentDidMount: function () {
    SystemStore.addChangeListener( this.handleSystemChange );
    // *Temp. Removed*
    // UpdateStore.addChangeListener( this.handleUpdateChange );

    SystemMiddleware.requestSystemInfo( "hardware" );
    SystemMiddleware.requestSystemInfo( "version" );
  }

  , componentWillUnmount: function () {
    SystemStore.removeChangeListener( this.handleSystemChange );
    // *Temp. Removed*
    // UpdateStore.removeChangeListener( this.handleUpdateChange );
  }

  , handleSystemChange: function () {
      this.setState({
        hardware : SystemStore.getSystemInfo( "hardware" )
        , version  : SystemStore.getSystemInfo( "version" )
      });
    }

  , handleUpdateChange: function () {
      this.setState({
        train    : UpdateStore.getUpdate( "get_current_train" )
        // TODO: Yet to add
        // , updates  : UpdateStore.getUpdate( "check_now_for_updates" )
      });
    }

  , render: function () {
    var memSize = round( ( this.state.hardware["memory-size"] / 1024 ) / 1024
                           , 1 );
    return (
      <Widget
        dimensions  =  { this.props.dimensions }
        position  =  { this.props.position }
        title      =  { this.props.title }
        size       =  { this.props.size }
        onMouseDownHolder = { this.props.onMouseDownHolder }
        refHolder = {this.props.refHolder} >

        <div className="wd-section wd-cpu-model">
          <span className="wd-title">CPU Model:</span>
          <span className="wd-value">{this.state.hardware["cpu-model"]}</span>
          <span className="wd-value">{"with " + this.state.hardware["cpu-cores"]
                                      + " cores."}</span>
        </div>
        <div className="wd-section wd-memory-size">
          <span className="wd-title">Memory Size:</span>
          <span className="wd-value">{memSize + " MB"}</span>
        </div>
        <div className="wd-section wd-version">
          <span className="wd-title">Version:</span>
          <span className="wd-value">{this.state.version}</span>
        </div>
        <div className="wd-section wd-train">
          <span className="wd-title">Current Update Train:</span>
          <span className="wd-value">{this.state.train}</span>
        </div>


      </Widget>
    );
  }
});

module.exports = SystemInfo;

/* Temp. Removed
        <div className="wd-section wd-update">
          <span className="wd-title">Available updates:</span>
          <span className="wd-value">{this.state.updates}</span>
        </div>
*/

