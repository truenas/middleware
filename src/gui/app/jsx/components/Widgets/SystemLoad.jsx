"use strict";

var React   =   require("react");

var Widget  =   require("../Widget");
var StatdWidgetContentHandler = require("./StatdWidgetContentHandler");

var SystemMiddleware = require("../../middleware/SystemMiddleware");
var SystemStore      = require("../../stores/SystemStore");

var SystemLoad = React.createClass({
  getInitialState: function() {
    return {
      statdResources:    [   {variable:"longterm", dataSource:"localhost.load.load.longterm", name:"Longterm Load", color:"#292929"}
                           , {variable:"midterm", dataSource:"localhost.load.load.midterm", name:"Midterm Load", color:"#a47f1a"}
                           , {variable:"shortterm", dataSource:"localhost.load.load.shortterm", name:"Shortterm Load", color:"#4a95b3"}
                         ]
    , chartTypes:        [  {   type:"line"
                              , primary: this.primaryChart("line")
                              , y:function(d) { if(d[1] === "nan") { return null; } else { return (Math.round(d[1] * 100) / 100); } }
                            }
                           ,{   type:"stacked"
                              , primary: this.primaryChart("stacked")
                              , y:function(d) { if(d[1] === "nan") { return null; } else { return (Math.round(d[1] * 100) / 100); } }
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
    var widgetIdentifier = "SystemLoad";
    return (
      <Widget
        positionX  =  { this.props.positionX }
        positionY  =  { this.props.positionY }
        title      =  { this.props.title }
        size       =  { this.props.size } >

        <StatdWidgetContentHandler
          widgetIdentifier  =  { widgetIdentifier }
          statdResources    =  { this.state.statdResources }
          chartTypes        =  { this.state.chartTypes } >
        </StatdWidgetContentHandler>

      </Widget>
    );
  }
});


module.exports = SystemLoad;