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
        hardware   :   ""
      , version    :   ""
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
      this.setState({  hardware       :   getSystemInfoFromStore( "hardware" )
                      ,version        :   getSystemInfoFromStore( "version" )
                    });
    }


 , requestData: function() {

    SystemMiddleware.requestSystemInfo( "hardware" );
    SystemMiddleware.requestSystemInfo( "version" );

  }

  , render: function() {
    //console.log(this.state.widgetData);
    // <h3 style={elementStyle}>{"It works! "}{this.state.widgetData}</h3>
    var memSize = (this.state.hardware["memory-size"] / 1024) / 1024;
    return (
      <Widget
        positionX  =  {this.props.positionX}
        positionY  =  {this.props.positionY}
        title      =  {this.props.title}
        size       =  {this.props.size} >
        <dl>
          <dt>CPU Model:</dt><dd>{this.state.hardware["cpu-model"]}</dd>
          <dt>Memory Size:</dt><dd>{memSize}MB</dd>
          <dt>Version:</dt><dd>{this.state.version}MB</dd>
        </dl>

      </Widget>
    );
  }
});


module.exports = SystemInfo;