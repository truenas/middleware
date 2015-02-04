/** @jsx React.DOM */

// Networks
// ========
// View showing network information, link state, VLANs, and other entities.
// For now, just interfaces.

"use strict";


var React  = require("react");

var Viewer      = require("../components/Viewer");
//var NetworksView = require("../views/Networks/NetworksView");

var NetworksMiddleware = require("../middleware/NetworksMiddleware");
var NetworksStore      = require("../stores/NetworksStore");

var viewData = {
    format  : require("../../data/middleware-keys/networks-display.json")[0]
  , routing : {
      "route" : "networks-editor"
    , "param" : "networkID"
  }
  , display: {
      filterCriteria: {
          connected: {
              name     : "connected interfaces"
            , testProp : { "link-state": "LINK_STATE_UP" }
          }
       , disconnected: {
              name     : "disconnected interfaces"
           , testprop : { "link-state": "LINK_STATE_DOWN" }
         }
        , unknown: {
              name     : "invalid or unknown interfaces"
            , testprop : { "link-state": "LINK_STATE_UNKNOWN" }
          }
      }
    , remainingName  : "other interfaces"
    , ungroupedName  : "all interfaces"
    , allowedFilters : [ ]
    , defaultFilters : [ "unknown" ]
    , allowedGroups  : [ "connected", "disconnected" ]
    , defaultGroups  : [ "connected", "disconnected" ]
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
  }

  , componentWillUnmount: function() {
    NetworksStore.removeChangeListener( this.handleNetworksChange );
  }

  , handleNetworksChange: function() {
      this.setState( getNetworksFromStore() );
  }

  , render: function() {
    return (
      <main>
        <h2>Networks</h2>
        <Viewer header      = { "Networks" }
                inputData   = { this.state.networksList }
                viewData    = { viewData }
                Editor      = { this.props.activeRouteHandler } />
      </main>
    );
  }
});

module.exports = Networks;
