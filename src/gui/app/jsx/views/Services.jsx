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
    , remainingName  : "other services"
    , ungroupedName  : "all services"
    , allowedFilters : [ ]
    , defaultFilters : [ ]
    , allowedGroups  : [ "running", "stopped" ]
    , defaultGroups  : [ "running", "stopped" ]
    , ShowToggleSwitch : true
  }
};

function getServicesFromStore() {
  return {
    servicesList: ServicesStore.getAllServices()
  };
}

var Services = React.createClass({

    getInitialState: function() {
      return getServicesFromStore();
    }

  , componentDidMount: function() {
      ServicesMiddleware.requestServicesList();

      ServicesStore.addChangeListener( this.handleServicesChange );
    }

  , componentWillUnmount: function() {
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
