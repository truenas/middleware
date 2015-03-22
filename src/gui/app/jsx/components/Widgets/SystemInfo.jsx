"use strict";

var React   =   require("react");
var moment  =   require("moment");

var Widget  = 	require("../Widget");

var SystemMiddleware = require("../../middleware/SystemMiddleware");
var SystemStore      = require("../../stores/SystemStore");

var UpdateMiddleware = require("../../middleware/UpdateMiddleware");
var UpdateStore      = require("../../stores/UpdateStore");

 function getSystemInfoFromStore( name ) {
 return SystemStore.getSystemInfo( name );
 }

 function getUpdateFromStore( name ) {
 return UpdateStore.getUpdate( name );
 }

var SystemInfo = React.createClass({
  getInitialState: function() {
    return {
        hardware   :   ""
      , version    :   ""
      , updates    :   ""
      , train      :   ""
    };
  }
  , componentDidMount: function() {
    this.requestData();

    SystemStore.addChangeListener( this.handleChange );
    UpdateStore.addChangeListener( this.handleChange );
 }

  , componentWillUnmount: function() {
     SystemStore.removeChangeListener( this.handleChange );
     UpdateStore.removeChangeListener( this.handleChange );
  }

 , handleChange: function() {
      this.setState({   hardware       :   getSystemInfoFromStore( "hardware" )
                      , version        :   getSystemInfoFromStore( "version" )
                      , updates        :   getUpdateFromStore( "check_now_for_updates" )
                      , train          :   getUpdateFromStore( "get_current_train" )
                    });
    }


 , requestData: function() {

    SystemMiddleware.requestSystemInfo( "hardware" );
    SystemMiddleware.requestSystemInfo( "version" );
    UpdateMiddleware.requestUpdateInfo( "check_now_for_updates" );
    UpdateMiddleware.requestUpdateInfo( "get_current_train" );

  }

  , render: function() {
    var memSize = (this.state.hardware["memory-size"] / 1024) / 1024;
    return (
      <Widget
        positionX  =  {this.props.positionX}
        positionY  =  {this.props.positionY}
        title      =  {this.props.title}
        size       =  {this.props.size} >
        <div className="wd-section wd-cpu-model">
          <span className="wd-title">CPU Model:</span>
          <span className="wd-value">{this.state.hardware["cpu-model"]}</span>
          <span className="wd-value">{"with " + this.state.hardware["cpu-cores"] + " cores."}</span>
        </div>
        <div className="wd-section wd-memory-size">
          <span className="wd-title">Memory Size:</span>
          <span className="wd-value">{memSize + " MB"}</span>
        </div>
        <div className="wd-section wd-version">
          <span className="wd-title">Version:</span>
          <span className="wd-value">{this.state.version}</span>
        </div>
        <div className="wd-section wd-train">
          <span className="wd-title">Cureent Update Train:</span>
          <span className="wd-value">{this.state.train}</span>
        </div>
        <div className="wd-section wd-update">
          <span className="wd-title">Available updates:</span>
          <span className="wd-value">{this.state.updates}</span>
        </div>

      </Widget>
    );
  }
});


module.exports = SystemInfo;