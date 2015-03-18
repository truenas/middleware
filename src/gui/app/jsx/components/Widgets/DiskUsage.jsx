"use strict";

var React   =   require("react");

var Widget  =   require("../Widget");
var DummyWidgetContent = require("./DummyWidgetContent");

var SystemMiddleware = require("../../middleware/SystemMiddleware");
var SystemStore      = require("../../stores/SystemStore");

function getSystemDeviceFromStore( name ) {
  return SystemStore.getSystemDevice( name );
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
    SystemStore.addChangeListener( this.handleChange );
  }

, componentWillUnmount: function() {
     SystemStore.removeChangeListener( this.handleChange );
  }

, requestData: function() {

    SystemMiddleware.requestSystemDevice( "disk" );
  }

, handleChange: function() {
    this.setState({ disk  : getSystemDeviceFromStore( "disk" ) });
    //console.log("DISK");
    //console.log(this.state.disk);
    if (this.state.disk !== undefined)
     {      
       var disk = this.state.disk[this.state.disk.length - 1]["name"];
       this.setState({  statdResources:    [  {variable:"write", dataSource:"localhost.disk-" + disk + ".disk_octets.write", name: disk + " Write", color:"#9ecc3c"}
                                            , {variable:"read", dataSource:"localhost.disk-" + disk + ".disk_octets.read", name: disk + " Read", color:"#77c5d5"}
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