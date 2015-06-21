

"use strict";

import React from "react";

import SystemMiddleware from "../../middleware/SystemMiddleware";
import SystemStore from "../../stores/SystemStore";

import chartHandler from "./mixins/chartHandler";

import round from "round";

var statdResources = [
    {
      variable      : "wiredData"
      , dataSource  : "localhost.memory.memory-wired.value"
      , name        : "Wired Memory"
      , color       : "#f39400"
    }
  , {
      variable      : "cacheData"
      , dataSource  : "localhost.memory.memory-cache.value"
      , name        : "Cached Memory"
      , color       : "#8ac007"
    }
  , {
      variable      : "activeData"
      , dataSource  : "localhost.memory.memory-active.value"
      , name        : "Active Memory"
      , color       : "#c9d200"
    }
  , {
      variable      : "freeData"
      , dataSource  : "localhost.memory.memory-free.value"
      , name        : "Free Memory"
      , color       : "#5186ab"
    }
  , {
      variable      : "inactiveData"
      , dataSource  : "localhost.memory.memory-inactive.value"
      , name        : "Inactive Memory"
      , color       : "#b6d5e9"
    }
];

var MemoryUtil = React.createClass({

  mixins: [ chartHandler ]

  , getInitialState: function () {
      return {    hardware: SystemStore.getSystemInfo( "hardware" )
                , statdResources : statdResources
                , chartTypes : []
                , widgetIdentifier : "MemoryUtil"

             };
    }

  , componentDidMount: function () {
      SystemStore.addChangeListener( this.handleChange );

      SystemMiddleware.requestSystemInfo( "hardware" );
    }

  , componentWillUnmount: function () {
      SystemStore.removeChangeListener( this.handleChange );
    }

  , primaryChart: function ( type ) {
      if ( this.props.primary === undefined && type === "line" ) {
        return true;
      } else if ( type === this.props.primary ) {
        return true;
      } else {
        return false;
      }
    }

  , handleChange: function () {
      var newState = {};
      newState.hardware = SystemStore.getSystemInfo( "hardware" );

      if ( newState.hardware ) {

        newState.chartTypes = [
                                {
                                  type    : "stacked"
                                  , primary : this.primaryChart( "stacked" )
                                  , y: function ( d ) {
                                    return round( ( d[1] / 1024 ) / 1024, .01 );
                                  }
                                }
                              , {
                                  type    : "line"
                                  , primary : this.primaryChart( "line" )
                                  , forceY  : [ 0, 100 ]
                                  , yUnit   : "%"
                                  , y: function ( d ) {
                                    return round( ( ( d[1] / newState.hardware["memory-size"] ) * 100 ), 0.01 ); }.bind( this )
                                }
                              , {
                                  type   : "pie"
                                  , primary: this.primaryChart( "pie" )
                                }
                            ];

        this.setState( newState );
      }
    }



});

module.exports = MemoryUtil;
