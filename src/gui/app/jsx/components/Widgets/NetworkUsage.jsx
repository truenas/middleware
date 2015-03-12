"use strict";

var React   =   require("react");

var Widget  =   require("../Widget");
var DummyWidgetContent = require("./DummyWidgetContent");

var NetworkUsage = React.createClass({
 getInitialState: function() {
   return {
     statdResources:    [  {variable:"octetsRx", dataSource:"localhost.interface-em0.if_octets.rx", name:"Octets Receive", color:"#3C696E"}
                          ,{variable:"octetsTx", dataSource:"localhost.interface-em0.if_octets.tx", name:"Octets Transmit", color:"#368D97"}
                          ,{variable:"packetsRx", dataSource:"localhost.interface-em0.if_packets.rx", name:"Packets Receive", color:"#A8E077"}
                          ,{variable:"packetsTx", dataSource:"localhost.interface-em0.if_packets.tx", name:"Packets Transmit", color:"#D9E35D"}
                          ,{variable:"errorsTx", dataSource:"localhost.interface-em0.if_errors.rx", name:"Errors Receive", color:"#C9653A"}
                          ,{variable:"errorsRx", dataSource:"localhost.interface-em0.if_errors.tx", name:"Errors Transmit", color:"#BE6F6F"}
                        ]
   , systemResources:   [  {variable:"hardware", dataSource:"hardware", subArray:"memory-size"}   
                        ]

   , chartTypes:        [  {type:"stacked", primary:"false"}
                          ,{type:"line", primary:"true"}
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