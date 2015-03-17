"use strict";

var React   =   require("react");

var Widget  =   require("../Widget");
var DummyWidgetContent = require("./DummyWidgetContent");

var NetworkUsage = React.createClass({
 getInitialState: function() {
  var iface = this.props.iface || "igb0";
   return {
     statdResources:    [  {variable:"octetsRx", dataSource:"localhost.interface-" + iface + ".if_octets.rx", name:"Data Receive (kB/s)", color:"#3C696E", area: true}
                          ,{variable:"octetsTx", dataSource:"localhost.interface-" + iface + ".if_octets.tx", name:"Data Transmit  (kB/s)", color:"#368D97", area: true}
                          ,{variable:"packetsRx", dataSource:"localhost.interface-" + iface + ".if_packets.rx", name:"Packets Receive", color:"#A8E077", area: true}
                          ,{variable:"packetsTx", dataSource:"localhost.interface-" + iface + ".if_packets.tx", name:"Packets Transmit", color:"#D9E35D", area: true}
                          ,{variable:"errorsTx", dataSource:"localhost.interface-" + iface + ".if_errors.rx", name:"Errors Receive", color:"#C9653A"}
                          ,{variable:"errorsRx", dataSource:"localhost.interface-" + iface + ".if_errors.tx", name:"Errors Transmit", color:"#BE6F6F"}
                        ]
    , chartTypes:       [  {   type:"stacked"
                              , primary:false
                              , y:function(d) { if(d[1] === "nan") { return null; } else { return (Math.round(d[1] * 100) / 100)/1024; } }

                            }
                           ,{     type:"line"
                                , primary:true
                                , y:function(d) { if(d[1] === "nan") { return null; } else { return (Math.round(d[1] * 100) / 100)/1024; } }
                                , yUnit : ""

                            }
                         ]
    };
 }

, render: function() {

   return (
     <Widget
       positionX  =  {this.props.positionX}
       positionY  =  {this.props.positionY}
       title      =  {this.props.title}
       size       =  {this.props.size} >


       <DummyWidgetContent
         statdResources    =  {this.state.statdResources}
         systemResources   =  {this.state.systemResources}
         chartTypes        =  {this.state.chartTypes} >
       </DummyWidgetContent>


     </Widget>

   );
 }
});


module.exports = NetworkUsage;
