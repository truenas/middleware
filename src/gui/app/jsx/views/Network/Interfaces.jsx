// Interfaces
// ==========

"use strict";

var componentLongName = "Interfaces";

import React from "react";

import Viewer from "../../components/Viewer";

import IM from "../../middleware/InterfacesMiddleware";
import IS from "../../stores/InterfacesStore";

const VIEWER_DATA =
  { keyUnique     : "name"
  , keyPrimary    : "name"
  , keySecondary  : "type"

  , itemSchema    : IS.getInterfaceSchema()
  , itemLabels    : IS.getInterfaceLabels()

  , routeName     : "interfaces-editor"
  , routeParam    : "interfaceName"

  , textRemaining : "other interfaces"
  , textUngrouped : "all interfaces"

  , groupsInitial : new Set( [ "connected", "disconnected", "unknown" ] )
  , groupsAllowed : new Set( [ "connected", "disconnected", "unknown" ] )

  , columnsInitial : new Set( [ "name", "type", "enabled", "dhcp" ] )
  , columnsAllowed : new Set( [ "name", "type", "enabled", "dhcp" ] )

  , groupBy:
    { connected:
        { name: "connected interfaces"
        , testProp: function ( _interface ) {
            return _interface.status['link-state'] === 'LINK_STATE_UP';
          }
        }
    , disconnected:
        { name: "disconnected interfaces"
        , testProp: function ( _interface ) {
            return _interface.status['link-state'] === 'LINK_STATE_DOWN';
          }
        }
    , unknown:
        { name: "invalid or unknown interfaces"
        , testProp: function ( _interface ) {
            return _interface.status['link-state'] === 'LINK_STATE_UNKNOWN';
          }
        }
    }
  };

function getInterfacesFromStore () {
  return { interfacesList: IS.getAllInterfaces() };
}

const Interfaces = React.createClass(
  { getInitialState: function () {
      return getInterfacesFromStore();
    }

  , componentDidMount: function () {
      IS.addChangeListener( this.handleInterfacesChange );
      IM.requestInterfacesList();
      IM.subscribe( componentLongName );
    }

  , componentWillUnmount: function () {
      IS.removeChangeListener( this.handleInterfacesChange );
      IM.unsubscribe( componentLongName );
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
