"use strict";

var React   =   require("react");

var Widget  =   require("../Widget");
var StatdWidgetContentHandler = require("./StatdWidgetContentHandler");

var ZfsMiddleware = require("../../middleware/ZfsMiddleware");
var ZfsStore      = require("../../stores/ZfsStore");


var DiskUsage = React.createClass({
  getInitialState: function() {    
    return { 
      pool: ZfsStore.getZfsPoolGetDisks( "freenas-boot")    
    , chartTypes:        [  {   type:"line"
                              , primary: this.primaryChart("line")
                              , y:function(d) { if(d[1] === "nan") { return null; } else { return (Math.round((d[1]/1024) * 100) / 100); } }
                            }

                         ]    
    };
  }

, componentDidMount: function() {
    this.requestData();
    ZfsStore.addChangeListener( this.handleChange );
  }

, componentWillUnmount: function() {
    ZfsStore.removeChangeListener( this.handleChange );
  }

, requestData: function() {
    ZfsMiddleware.requestZfsPoolGetDisks( "freenas-boot" );
  }

, handleChange: function() {
    this.setState({ pool: ZfsStore.getZfsPoolGetDisks( "freenas-boot") });
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
    var widgetIdentifier = "DiskUsage";
    var statdResources = [];

    //console.log(this.state.pool);
    if (this.state.pool)    {
      var systemPoolPath = this.state.pool[0].split("/") ;
      var systemPoolName = systemPoolPath[systemPoolPath.length - 1].slice(0, systemPoolPath[systemPoolPath.length - 1].indexOf("p"));

          statdResources = [  {variable:"write", dataSource:"localhost.disk-" + systemPoolName + ".disk_octets.write", name: systemPoolName + " Write", color:"#9ecc3c"}
                              , {variable:"read", dataSource:"localhost.disk-" + systemPoolName + ".disk_octets.read", name: systemPoolName + " Read", color:"#77c5d5"}
                           ];
    }
    
    //console.log(statdResources);
      return (
        <Widget
          positionX  =  {this.props.positionX}
          positionY  =  {this.props.positionY}
          title      =  {this.props.title}
          size       =  {this.props.size} >

          <StatdWidgetContentHandler
            widgetIdentifier  =  {widgetIdentifier}
            statdResources    =  {statdResources}
            chartTypes        =  {this.state.chartTypes} >
          </StatdWidgetContentHandler>

        </Widget>
      );
    } 

  
});


module.exports = DiskUsage;