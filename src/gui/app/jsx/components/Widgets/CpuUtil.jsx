"use strict";

var React            =   require("react");

var chartHandler     =   require("./mixins/chartHandler");

var round            =   require("round");

var CpuUtil = React.createClass({

  mixins: [ chartHandler ]

, getInitialState: function() {
    return {
      statdResources:    [   {variable:"system", dataSource:"localhost.aggregation-cpu-sum.cpu-system.value", name:"System", color:"#9ecc3c"}
                           , {variable:"user", dataSource:"localhost.aggregation-cpu-sum.cpu-user.value", name:"User", color:"#77c5d5"}
                           , {variable:"nice", dataSource:"localhost.aggregation-cpu-sum.cpu-nice.value", name:"Nice", color:"#ffdb1a"}
                           , {variable:"idle", dataSource:"localhost.aggregation-cpu-sum.cpu-idle.value", name:"Idle", color:"#ed8b00"}
                           , {variable:"interrupt", dataSource:"localhost.aggregation-cpu-sum.cpu-interrupt.value", name:"Interrupt", color:"#cc3c3c"}
      ]
    , chartTypes:        [  {   type:"line"
                              , primary: this.primaryChart("line")
                              , y:function(d) { if(d[1] === "nan") { return null; } else { return (round(d[1], 0.01)); } }
                            }
                           ,{   type:"pie"
                              , primary: this.primaryChart("pie")
                            }
                         ]
    , widgetIdentifier : "CpuUtil"
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
});


module.exports = CpuUtil;
