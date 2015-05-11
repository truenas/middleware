// Network Middleware
// ==================

"use strict";

import MiddlewareClient from "../middleware/MiddlewareClient";

import NetworksActionCreators from "../actions/NetworksActionCreators";

module.exports = {

    subscribe: function( componentID ) {
      MiddlewareClient.subscribe( ["networks.changed"], componentID );
      MiddlewareClient.subscribe( ["task.*"], componentID );
    }

  , unsubscribe: function( componentID ) {
      MiddlewareClient.unsubscribe( ["networks.changed"], componentID );
      MiddlewareClient.unsubscribe( ["task.*"], componentID );
    }


  , requestNetworksList: function () {
      MiddlewareClient.request( "network.interfaces.query", [], function ( rawNetworksList ) {
        NetworksActionCreators.receiveNetworksList( rawNetworksList );
      });
    }

};
