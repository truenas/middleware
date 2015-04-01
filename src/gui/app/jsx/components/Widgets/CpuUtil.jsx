"use strict";

var React   =   require("react");

var Widget  =   require("../Widget");
var StatdWidgetContentHandler = require("./StatdWidgetContentHandler");

var SystemMiddleware = require("../../middleware/SystemMiddleware");
var SystemStore      = require("../../stores/SystemStore");

var CpuUtil = React.createClass({
  getInitialState: function() {
    return {
      statdResources:    [   {variable:"system", dataSource:"localhost.aggregation-cpu-sum.cpu-system.value", name:"System", color:"#9ecc3c"}
                           , {variable:"user", dataSource:"localhost.aggregation-cpu-sum.cpu-user.value", name:"User", color:"#77c5d5"}
                           , {variable:"nice", dataSource:"localhost.aggregation-cpu-sum.cpu-nice.value", name:"Nice", color:"#ffdb1a"}
                           , {variable:"idle", dataSource:"localhost.aggregation-cpu-sum.cpu-idle.value", name:"Idle", color:"#ed8b00"}
                           , {variable:"interrupt", dataSource:"localhost.aggregation-cpu-sum.cpu-interrupt.value", name:"Interrupt", color:"#cc3c3c"}
      ]
    , chartTypes:        [  {   type:"line"
                              , primary: this.primaryChart("line")
                              , y:function(d) { if(d[1] === "nan") { return null; } else { return (Math.round(d[1] * 100) / 100); } }
                            }
                           ,{   type:"pie"
                              , primary: this.primaryChart("pie")
                            }
                         ]
    };
  }

, primaryChart: function(type)
  {
    if (this.props.primary === undefined && type === "line")
    {
      return true;
    }
    else if (type === this.props.primary)
    {
      return true;
    }
    else
    {
      return false;
    }

  }
, render: function() {
    var widgetIdentifier = "CpuUtil";
    return (
      <Widget
        positionX  =  { this.props.positionX }
        positionY  =  { this.props.positionY }
        title      =  { this.props.title }
        size       =  { this.props.size } >

        <StatdWidgetContentHandler
          widgetIdentifier    =  { widgetIdentifier }
          statdResources      =  { this.state.statdResources }
          chartTypes          =  { this.state.chartTypes } >
        </StatdWidgetContentHandler>

      </Widget>
    );
  }
});


module.exports = CpuUtil;
