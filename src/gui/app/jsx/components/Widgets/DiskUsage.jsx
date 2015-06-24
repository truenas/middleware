

"use strict";

import React from "react";

import ZfsMiddleware from "../../middleware/ZfsMiddleware";
import PoolStore from "../../stores/PoolStore";

import chartHandler from "./mixins/chartHandler";

import round from "round";

var DiskUsage = React.createClass({

  mixins: [ chartHandler ]

  , getInitialState: function () {
    return {
      pool:              PoolStore.getDisksInBootPool()
      , statdResources:    []
      , chartTypes:        [  {   type: "line"
                                , primary: this.primaryChart( "line" )
                                , y: function ( d ) {
                                  return ( round( d[1] / 1024, 0.01 ) ); }
                              }
                           ]
      , widgetIdentifier : "DiskUsage"
    };
  }

  , componentDidMount: function () {
    PoolStore.addChangeListener( this.handleChange );
    ZfsMiddleware.requestPoolDisks( "freenas-boot" );
  }

  , componentWillUnmount: function () {
    PoolStore.removeChangeListener( this.handleChange );
  }

  , handleChange: function () {
    var newState = {};
    newState.pool = PoolStore.getDisksInBootPool();

    if ( newState.pool && newState.pool.length > 0 ) {
      var systemPoolPath = newState.pool[0].split( "/" ) ;
      var systemPoolName = systemPoolPath[systemPoolPath.length - 1]
                            .slice( 0, systemPoolPath[systemPoolPath.length - 1]
                            .indexOf( "p" ) );

      newState.statdResources = [
                                    {   variable: "write"
                                      , dataSource: "localhost.disk-"
                                        + systemPoolName
                                        + ".disk_octets.write"
                                      , name: systemPoolName + " Write"
                                      , color: "#9ecc3c"
                                    }
                                  , {   variable: "read"
                                      , dataSource: "localhost.disk-"
                                        + systemPoolName
                                        + ".disk_octets.read"
                                      , name: systemPoolName + " Read"
                                      , color: "#77c5d5"
                                    }
                                ];
      this.setState( newState );
    }


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

});


module.exports = DiskUsage;
