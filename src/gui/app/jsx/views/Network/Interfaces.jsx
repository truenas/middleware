// Interfaces
// ==========

"use strict";

var componentLongName = "Interfaces";

import React from "react";

import Viewer from "../../components/Viewer";

import InterfacesMiddleware from "../../middleware/InterfacesMiddleware";

import InterfacesStore from "../../stores/InterfacesStore";

const VIEWER_DATA =
  { keyUnique     : "id"
  , keyPrimary    : "id"
  , keySecondary  : "name"

  , itemSchema    : InterfacesStore.getInterfaceSchema()
  , itemLabels    : InterfacesStore.getInterfaceLabels()

  , routeName     : "interfaces-editor"
  , routeParam    : "interfaceID"

  , textRemaining : "other interfaces"
  , textUngrouped : "all interfaces"

  , groupsInitial : new Set( [ "connected", "disconnected", "unknown" ] )
  , groupsAllowed : new Set( [ "connected", "disconnected", "unknown" ] )

  , columnsInitial : new Set(
                      [ "id"
                      , "name"
                      , "type"
                      , "dhcp"
                      ]
                    )
  , columnsAllowed : new Set(
                      [ "id"
                      , "name"
                      , "type"
                      , "dhcp"
                      ]
                    )

  , groupBy:
    { connected:
       { name: "connected interfaces"
       , testProp: { "link-state": "LINK_STATE_UP" }
       }
    , disconnected:
       { name: "disconnected interfaces"
       , testProp: { "link-state": "LINK_STATE_DOWN" }
       }
    , unknown:
       { name: "invalid or unknown interfaces"
       , testProp: { "link-state": "LINK_STATE_UNKNOWN" }
       }
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
              header    = { "Interfaces" }
              itemData  = { this.state.interfacesList }
              { ...VIEWER_DATA } />;
  }

});

export default Interfaces;
