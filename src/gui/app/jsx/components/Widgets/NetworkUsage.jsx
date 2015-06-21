

"use strict";

var React   =   require( "react" );

import SystemMiddleware from "../../middleware/SystemMiddleware";
import SystemStore from "../../stores/SystemStore";

import chartHandler from "./mixins/chartHandler";

import round from "round";

var NetworkUsage = React.createClass({

  mixins: [ chartHandler ]

  , getInitialState: function () {
   return {
     network            : SystemStore.getSystemDevice( "network" )
     , statdResources   : []
     , chartTypes       : [
                                  {   type: "stacked"
                                    , primary: false
                                    , y: function ( d ) {
                                      return ( round( d[1] / 1024, 0.01 ) ); }
                                  }
                                , {   type: "line"
                                    , primary: true
                                    , y: function ( d ) {
                                      return ( round( d[1] / 1024, 0.01 ) ); }
                                    , yUnit : ""
                                  }
                                ]
     , widgetIdentifier : "NetworkUsage"
   };
 }
  , componentDidMount: function () {
    SystemStore.addChangeListener( this.handleChange );
    SystemMiddleware.requestSystemDevice( "network" );
  }

  , componentWillUnmount: function () {
    SystemStore.removeChangeListener( this.handleChange );
  }

  , handleChange: function () {
    var newState = {};
    newState.network  = SystemStore.getSystemDevice( "network" );

    if ( newState.network ) {
      var iface = newState.network[0]["name"];
      newState.statdResources = [
                                  {
                                    variable: "octetsRx"
                                    , dataSource: "localhost.interface-"
                                                  + iface + ".if_octets.rx"
                                    , name: "Data Receive (kB/s)"
                                    , color: "#3C696E"
                                    , area: true
                                  }
                                , {
                                    variable: "octetsTx"
                                    , dataSource: "localhost.interface-"
                                                  + iface + ".if_octets.tx"
                                    , name: "Data Transmit  (kB/s)"
                                    , color: "#368D97"
                                    , area: true
                                  }
                                , {
                                    variable: "packetsRx"
                                    , dataSource: "localhost.interface-"
                                                  + iface + ".if_packets.rx"
                                    , name: "Packets Receive"
                                    , color: "#A8E077"
                                    , area: true
                                  }
                                , {
                                    variable: "packetsTx"
                                    , dataSource: "localhost.interface-"
                                                  + iface + ".if_packets.tx"
                                    , name: "Packets Transmit"
                                    , color: "#D9E35D"
                                    , area: true
                                  }
                                , {
                                    variable: "errorsTx"
                                    , dataSource: "localhost.interface-"
                                                  + iface + ".if_errors.rx"
                                    , name: "Errors Receive"
                                    , color: "#C9653A"
                                  }
                                , {
                                    variable: "errorsRx"
                                    , dataSource: "localhost.interface-"
                                                  + iface + ".if_errors.tx"
                                    , name: "Errors Transmit"
                                    , color: "#BE6F6F"
                                  }
                                ];

      this.setState( newState );
    }
  }

});


module.exports = NetworkUsage;
