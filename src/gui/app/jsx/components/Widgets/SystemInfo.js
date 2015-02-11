/** @jsx React.DOM */

"use strict";

var React   =   require("react");
var moment  =   require("moment");

var Widget  = 	require("../Widget");

var SystemMiddleware = require("../../middleware/SystemMiddleware");
var SystemStore      = require("../../stores/SystemStore");

 function getSystemInfoFromStore( name ) {
 return SystemStore.getSystemInfo( name );
 }

var SystemInfo = React.createClass({
  getInitialState: function() {
    return {
       cpuModel      :   ""
      ,memorySize    :   ""
    };
  }
  , componentDidMount: function() {
    this.requestData();

    SystemStore.addChangeListener( this.handleStatdChange );
 }

  , componentWillUnmount: function() {
     SystemStore.removeChangeListener( this.handleStatdChange );
  }

 , handleStatdChange: function() {
      this.setState({  cpuModel       :   getSystemInfoFromStore( "cpu_model" )
                      ,memorySize     :   getSystemInfoFromStore( "memory_size" )
                    });
    }


 , requestData: function() {

    SystemMiddleware.requestSystemInfo( "cpu_model" );
    SystemMiddleware.requestSystemInfo( "memory_size" );

  }

  , render: function() {
    //console.log(this.state.widgetData);
    // <h3 style={elementStyle}>{"It works! "}{this.state.widgetData}</h3>
    var memSize = (this.state.memorySize / 1024) / 1024;
    return (
      <Widget
        positionX  =  {this.props.positionX}
        positionY  =  {this.props.positionY}
        title      =  {this.props.title}
        size       =  {this.props.size} >

        <dl>
          <dt>CPU Model:</dt><dd>{this.state.cpuModel}</dd>
          <dt>Memory Size:</dt><dd>{memSize}MB</dd>
        </dl>

      </Widget>
    );
  }
});


module.exports = SystemInfo;