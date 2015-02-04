// Network Middleware
// ==================

"use strict";

var MiddlewareClient = require("../middleware/MiddlewareClient");

var NetworksActionCreators = require("../actions/NetworksActionCreators")

module.exports = {

  requestNetworksList: function() {
      MiddlewareClient.request( "networkd.configuration.query_interfaces", [], function ( rawNetworksList ) {
        NetworksActionCreators.receiveNetworksList( rawNetworksList );
      });
  }

};
