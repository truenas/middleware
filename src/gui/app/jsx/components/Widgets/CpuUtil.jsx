

"use strict";

import React from "react";
import chartHandler from "./mixins/chartHandler";
import round from "round";

var CpuUtil = React.createClass({

  mixins: [ chartHandler ]

  , getInitialState: function () {
    var dataSrc = "localhost.aggregation-cpu-sum."
    return {
      statdResources: [   {variable: "system"
                           , dataSource: dataSrc + "cpu-system.value"
                           , name: "System"
                           , color: "#9ecc3c"}
                         , {variable: "user"
                            , dataSource: dataSrc + "cpu-user.value"
                            , name: "User"
                            , color: "#77c5d5"}
                         , {variable: "nice"
                            , dataSource: dataSrc + "cpu-nice.value"
                            , name: "Nice"
                            , color: "#ffdb1a"}
                         , {variable: "idle"
                            , dataSource: dataSrc + "cpu-idle.value"
                            , name: "Idle"
                            , color: "#ed8b00"}
                         , {variable: "interrupt"
                            , dataSource: dataSrc + "cpu-interrupt.value"
                            , name: "Interrupt"
                            , color: "#cc3c3c"}
      ]
      , chartTypes:   [   {type: "line"
                           , primary: this.primaryChart( "line" )
                           , y: function ( d ) {
                              return ( round( d[1], 0.01 ) ); }
                          }
                        , {   type: "pie"
                            , primary: this.primaryChart( "pie" )
                          }
                      ]
      , widgetIdentifier : "CpuUtil"
    };
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


module.exports = CpuUtil;
