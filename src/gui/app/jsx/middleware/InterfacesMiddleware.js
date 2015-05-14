// Interfaces Middleware
// =====================

"use strict";

import MiddlewareClient from "../middleware/MiddlewareClient";

import InterfacesActionCreators from "../actions/InterfacesActionCreators";

module.exports = {

  subscribe: function ( componentID ) {
    MiddlewareClient.subscribe( [ "networks.changed" ], componentID );
    MiddlewareClient.subscribe( [ "task.*" ], componentID );
  }

  , unsubscribe: function ( componentID ) {
    MiddlewareClient.unsubscribe( [ "networks.changed" ], componentID );
    MiddlewareClient.unsubscribe( [ "task.*" ], componentID );
  }

  , requestInterfacesList: function () {
      MiddlewareClient.request( "network.interfaces.query"
                              , []
                              , function ( rawInterfacesList ) {
        InterfacesActionCreators.receiveInterfacesList( rawInterfacesList );
      });
    }

};
