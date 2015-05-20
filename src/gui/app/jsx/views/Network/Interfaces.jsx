// Interfaces
// ==========

"use strict";

var componentLongName = "Interfaces";

import React from "react";

import Viewer from "../../components/Viewer";

import InterfacesMiddleware from "../../middleware/InterfacesMiddleware";

import InterfacesStore from "../../stores/InterfacesStore";

var viewData = {
  format: require( "../../../data/middleware-keys/interfaces-display.json" )[0]
  , routing: { route : "interfaces-editor"
             , param : "interfaceID"
             }
  , display: { filterCriteria:
               { connected:
                 { name: "connected interfaces"
                 , testProp: { link_state: "LINK_STATE_UP" }
                 }
               , disconnected:
                 { name: "disconnected interfaces"
                 , testprop: { link_state: "LINK_STATE_DOWN" }
                }
               , unknown:
                 { name: "invalid or unknown interfaces"
                 , testprop: { link_state: "LINK_STATE_UNKNOWN" }
                 }
               }
             , remainingName: "other interfaces"
             , ungroupedName: "all interfaces"
             , allowedFilters: [ ]
             , defaultFilters: [ ]
             , allowedGroups: [ "connected"
                              , "disconnected"
                              , "unknown" ]
             , defaultGroups: [ "connected"
                              , "disconnected"
                              , "unknown" ]
             , defaultCollapsed: [ "unknown" ]
            }
};

function getInterfacesFromStore () {
  return { interfacesList: InterfacesStore.getAllInterfaces() };
}

const Interfaces = React.createClass({

  getInitialState: function () {
    return getInterfacesFromStore();
  }

  , componentDidMount: function () {
    InterfacesStore.addChangeListener( this.handleInterfacesChange );
    InterfacesMiddleware.requestInterfacesList();
    InterfacesMiddleware.subscribe( componentLongName );
  }

  , componentWillUnmount: function () {
    InterfacesStore.removeChangeListener( this.handleInterfacesChange );
    InterfacesMiddleware.unsubscribe( componentLongName );
  }

  , handleInterfacesChange: function () {
    this.setState( getInterfacesFromStore() );
  }

  , render: function () {
      return <Viewer
               header = { "Interfaces" }
               inputData = { this.state.interfacesList }
               viewData = { viewData } />;
    }

});

export default Interfaces;
