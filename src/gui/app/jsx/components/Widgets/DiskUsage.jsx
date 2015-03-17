"use strict";

var React   =   require("react");

var Widget  =   require("../Widget");
var DummyWidgetContent = require("./DummyWidgetContent");

var SystemMiddleware = require("../../middleware/SystemMiddleware");
var SystemStore      = require("../../stores/SystemStore");

var DiskUsage = React.createClass({
  getInitialState: function() {
    var disk = this.props.disk || "ada0";
    return {
      statdResources:    [   {variable:"write", dataSource:"localhost.disk-" + disk + ".disk_octets.write", name: disk + " Write", color:"#9ecc3c"}
                           , {variable:"read", dataSource:"localhost.disk-" + disk + ".disk_octets.read", name: disk + " Read", color:"#77c5d5"}
                         ]
    , chartTypes:        [  {   type:"line"
                              , primary: this.primaryChart("line")
                              , y:function(d) { if(d[1] === "nan") { return null; } else { return (Math.round(d[1] * 100) / 100)/1024; } }
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
    return (
      <Widget
        positionX  =  {this.props.positionX}
        positionY  =  {this.props.positionY}
        title      =  {this.props.title}
        size       =  {this.props.size} >

        <DummyWidgetContent
          statdResources    =  {this.state.statdResources}
          chartTypes        =  {this.state.chartTypes} >
        </DummyWidgetContent>

      </Widget>
    );
  }
});


module.exports = DiskUsage;