// Networks
// ========
// View showing network information, link state, VLANs, and other entities.
// For now, just interfaces.

"use strict";

var componentLongName = "Networks";

var React  = require("react");

var Router       = require("react-router");
var RouteHandler = Router.RouteHandler;

var Viewer      = require("../components/Viewer");

var NetworksMiddleware = require("../middleware/NetworksMiddleware");
var NetworksStore      = require("../stores/NetworksStore");

var viewData = {
    format  : require("../../data/middleware-keys/networks-display.json")[0]
  , routing : {
      "route" : "networks-editor"
    , "param" : "networksID"
  }
  , display : {
      filterCriteria: {
          connected: {
              name     : "connected interfaces"
            , testProp : { "link_state": "LINK_STATE_UP" }
          }
       , disconnected: {
              name     : "disconnected interfaces"
           , testprop : { "link_state": "LINK_STATE_DOWN" }
         }
        , unknown: {
              name     : "invalid or unknown interfaces"
            , testprop : { "link_state": "LINK_STATE_UNKNOWN" }
          }
      }
    , remainingName    : "other interfaces"
    , ungroupedName    : "all interfaces"
    , allowedFilters   : [ ]
    , defaultFilters   : [ ]
    , allowedGroups    : [ "connected", "disconnected", "unknown" ]
    , defaultGroups    : [ "connected", "disconnected", "unknown" ]
    , defaultCollapsed : [ "unknown" ]
  }
};

function getNetworksFromStore() {
  return {
    networksList : NetworksStore.getAllNetworks()
  };
}

var Networks = React.createClass({

    getInitialState: function() {
      return getNetworksFromStore();
    }

  , componentDidMount: function() {
    NetworksStore.addChangeListener( this.handleNetworksChange );
    NetworksMiddleware.requestNetworksList();
    NetworksMiddleware.subscribe( componentLongName );
  }

  , componentWillUnmount: function() {
    NetworksStore.removeChangeListener( this.handleNetworksChange );
    NetworksMiddleware.unsubscribe( componentLongName );
  }

  , handleNetworksChange: function() {
      this.setState( getNetworksFromStore() );
  }

  , render: function() {
      return <Viewer header      = { "Networks" }
                     inputData   = { this.state.networksList }
                     viewData    = { viewData }
                     Editor      = { RouteHandler } />;
    }

});

module.exports = Networks;
