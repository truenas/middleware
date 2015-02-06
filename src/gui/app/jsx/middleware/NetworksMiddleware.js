// Network Middleware
// ==================

"use strict";

var MiddlewareClient = require("../middleware/MiddlewareClient");

var NetworksActionCreators = require("../actions/NetworksActionCreators");

module.exports = {

    subscribe: function() {
      MiddlewareClient.subscribe( ["networks.changed"] );
      MiddlewareClient.subscribe( ["task.*"] );
    }

  , unsubscribe: function() {
      MiddlewareClient.unsubscribe( ["networks.changed"] );
      MiddlewareClient.unsubscribe( ["task.*"] );
    }


  , requestNetworksList: function() {
      MiddlewareClient.request( "network.interfaces.query", [], function ( rawNetworksList ) {
        NetworksActionCreators.receiveNetworksList( rawNetworksList );
      });
    }

};
