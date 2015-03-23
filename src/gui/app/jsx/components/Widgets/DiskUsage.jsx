"use strict";

var React   =   require("react");

var Widget  =   require("../Widget");
var DummyWidgetContent = require("./DummyWidgetContent");

var ZfsMiddleware = require("../../middleware/ZfsMiddleware");
var ZfsStore      = require("../../stores/ZfsStore");

function getZfsPoolGetDisksFromStore( name ) {
  return ZfsStore.getZfsPoolGetDisks( name );
}


var DiskUsage = React.createClass({
  getInitialState: function() {
    //var disk = this.props.disk || "ada0";
    return {
      statdResources:    []
    , chartTypes:        [  {   type:"line"
                              , primary: this.primaryChart("line")
                              , y:function(d) { if(d[1] === "nan") { return null; } else { return (Math.round((d[1]/1024) * 100) / 100); } }
                            }
                           
                         ]
    , ready:            false
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
    this.setState({ pool  : getZfsPoolGetDisksFromStore( "freenas-boot") });    
    if (this.state.pool !== undefined)
    {
      var systemPoolPath = this.state.pool[0].split("/")     
      var systemPoolName = systemPoolPath[systemPoolPath.length - 1].slice(0, systemPoolPath[systemPoolPath.length - 1].indexOf("p"))

      this.setState({  statdResources:    [  {variable:"write", dataSource:"localhost.disk-" + systemPoolName + ".disk_octets.write", name: systemPoolName + " Write", color:"#9ecc3c"}
                                            , {variable:"read", dataSource:"localhost.disk-" + systemPoolName + ".disk_octets.read", name: systemPoolName + " Read", color:"#77c5d5"}
                                           ]
                      , ready:             true
                    });

    }
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
  if (this.state.ready === false)
    {
      return (
        <Widget
          positionX  =  {this.props.positionX}
          positionY  =  {this.props.positionY}
          title      =  {this.props.title}
          size       =  {this.props.size} >

          <div>Loading...</div>

        </Widget>
      );
    }
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