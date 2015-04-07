"use strict";

var React   =   require("react");

var Widget  =   require("../Widget");
var StatdWidgetContentHandler = require("./StatdWidgetContentHandler");

var SystemMiddleware = require("../../middleware/SystemMiddleware");
var SystemStore      = require("../../stores/SystemStore");


var chartTypes = [
    {   type:"stacked"
      , primary:false
      , y:function(d) { if(d[1] === "nan") { return null; } else { return (Math.round((d[1]/1024) * 100) / 100); } }
    }
   ,{   type:"line"
      , primary:true
      , y:function(d) { if(d[1] === "nan") { return null; } else { return (Math.round((d[1]/1024) * 100) / 100); } }
      , yUnit : ""
    }
  ];

var NetworkUsage = React.createClass({
 getInitialState: function() {
   return { network  : SystemStore.getSystemDevice( "network" ) };
 }
, componentDidMount: function() {
    SystemStore.addChangeListener( this.handleChange );
    SystemMiddleware.requestSystemDevice( "network" );
  }

, shouldComponentUpdate: function(nextProps, nextState) {
    return nextProps.network !== this.state.network;
}

, componentWillUnmount: function() {
     SystemStore.removeChangeListener( this.handleChange );
  }

, handleChange: function() {
    this.setState({ network  : SystemStore.getSystemDevice( "network" ) });
  }

, render: function() {
   var widgetIdentifier = "NetworkUsage";
   var statdResources = [];

    if (this.state.network)
     {
       var iface = this.state.network[0]["name"];
       statdResources = [
                          {   variable:"octetsRx"
                            , dataSource:"localhost.interface-" + iface + ".if_octets.rx"
                            , name:"Data Receive (kB/s)"
                            , color:"#3C696E"
                            , area: true
                          }
                         ,{   variable:"octetsTx"
                            , dataSource:"localhost.interface-" + iface + ".if_octets.tx"
                            , name:"Data Transmit  (kB/s)"
                            , color:"#368D97"
                            , area: true
                          }
                         ,{
                              variable:"packetsRx"
                            , dataSource:"localhost.interface-" + iface + ".if_packets.rx"
                            , name:"Packets Receive"
                            , color:"#A8E077"
                            , area: true
                          }
                         ,{
                              variable:"packetsTx"
                            , dataSource:"localhost.interface-" + iface + ".if_packets.tx"
                            , name:"Packets Transmit"
                            , color:"#D9E35D"
                            , area: true
                          }
                         ,{
                              variable:"errorsTx"
                            , dataSource:"localhost.interface-" + iface + ".if_errors.rx"
                            , name:"Errors Receive"
                            , color:"#C9653A"
                          }
                         ,{
                              variable:"errorsRx"
                            , dataSource:"localhost.interface-" + iface + ".if_errors.tx"
                            , name:"Errors Transmit"
                            , color:"#BE6F6F"
                          }
                        ];
      }

   return (
     <Widget
       positionX  =  {this.props.positionX}
       positionY  =  {this.props.positionY}
       title      =  {this.props.title}
       size       =  {this.props.size} >

       <StatdWidgetContentHandler
         widgetIdentifier  =  {widgetIdentifier}
         statdResources    =  {statdResources}
         chartTypes        =  {chartTypes} >
       </StatdWidgetContentHandler>

     </Widget>
   );
 }
});


module.exports = NetworkUsage;
