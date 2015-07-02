// Services
// =======
//

"use strict";

var componentLongName = "Services";

import React from "react";

import Viewer from "../components/Viewer";

import SM from "../middleware/ServicesMiddleware";
import SS from "../stores/ServicesStore";

var VIEWER_DATA =
  { keyUnique     : SS.uniqueKey
  , keyPrimary    : "name"
//  , keySecondary  : "id"

  , itemSchema    : SS.itemSchema
  , itemLabels    : SS.itemLabels

  , routeName     : "services-editor"
  , routeParam    : "serviceID"

  , textRemaining : "other services"
  , textUngrouped : "all services"

  , groupsInitial : new Set( [ "running", "stopped" ] )
  , groupsAllowed : new Set( [ "running", "stopped" ] )

  , filtersInitial :  new Set ( )
  , filtersAllowed : new Set ( [ "running", "stopped" ] )

  , columnsInitial : new Set (
                       [ "name"
                       , "pid"
                       , "state"
                       ]
                      )
  , columnsAllowed : new Set (
                       [ "name"
                       , "pid"
                       , "state"
                       ]
                      )
  , groupBy:
  { running:
    { name: "active services"
    , testProp: { state: "running" }
    }
  , stopped:
    { name        : "stopped services"
    , testProp  : { state: "stopped" }
    }
  }
};


function getServicesFromStore () {
  return { servicesList: SS.services };
}

const Services = React.createClass({

  getInitialState: function () {
      return getServicesFromStore();
    }

  , componentDidMount: function () {
      SM.requestServicesList();
      SM.subscribeToTask( componentLongName );

      SS.addChangeListener( this.handleServicesChange );
    }

  , componentWillUnmount: function () {
      SM.unsubscribeFromTask( componentLongName );
      SS.removeChangeListener( this.handleServicesChange );
    }

  , handleServicesChange: function () {
      this.setState( getServicesFromStore() );
    }

  , render: function () {
    return (
      <main>
        <h2>Services</h2>
        <Viewer header      = { "Services" }
                itemData   = { this.state.servicesList }
                { ...VIEWER_DATA } />
      </main>
    );
  }
});

export default Services;
