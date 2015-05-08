// Services
// =======
//

"use strict";


var React = require("react");

var Viewer = require("../components/Viewer");

var ServicesMiddleware = require("../middleware/ServicesMiddleware");
var ServicesStore      = require("../stores/ServicesStore");

var viewData = {
    format  : require("../../data/middleware-keys/services-display.json")[0]
  , routing : {
      "route" : "services-editor"
    , "param" : "serviceID"
  }
  , display: {
      filterCriteria: {
          running: {
              name     : "active services"
            , testProp : { "state": "running" }
          }
        , stopped: {
              name     : "stopped services"
            , testProp : { "state": "stopped" }
          }
      }
    , remainingName    : "other services"
    , ungroupedName    : "all services"
    , allowedFilters   : [ ]
    , defaultFilters   : [ ]
    , allowedGroups    : [ "running", "stopped" ]
    , defaultGroups    : [ "running", "stopped" ]
    , showToggleSwitch : true
    , handleToggle     : handleToggle
  }
};

function getServicesFromStore() {
  return {
    servicesList: ServicesStore.getAllServices()
  };
}

function handleToggle( serviceObj, toggled ) {
      var serviceName   = serviceObj.name;
      var serviceState  = serviceObj.state;

      var action = (serviceState === "running" ? "stop" : "start");

      ServicesMiddleware.updateService(serviceName, action);

      //TODO: Select the service with changing state.
    }


var Services = React.createClass({

    getInitialState: function() {
      return getServicesFromStore();
    }

  , componentDidMount: function() {
      ServicesMiddleware.requestServicesList();
      ServicesMiddleware.subscribeToTask( "Services Viewer" );

      ServicesStore.addChangeListener( this.handleServicesChange );
    }

  , componentWillUnmount: function() {
      ServicesMiddleware.unsubscribeFromTask( "Services Viewer" );
      ServicesStore.removeChangeListener( this.handleServicesChange );
    }

  , handleServicesChange: function() {
      this.setState( getServicesFromStore() );
    }

  , render: function() {
    return (
      <main>
        <h2>Services</h2>
        <Viewer header      = { "Services" }
                inputData   = { this.state.servicesList }
                viewData    = { viewData } />
      </main>
    );
  }
});

module.exports = Services;
