// Network Config Middleware
// =========================

"use strict";

import MiddlewareClient from "../middleware/MiddlewareClient";

import NetworkConfigActionCreators
  from "../actions/NetworkConfigActionCreators";

class NetworkConfigMiddleware {

  subscribe ( componentID ) {
    MiddlewareClient.subscribe( [ "network.changed" ], componentID );
    MiddlewareClient.subscribe( [ "task.*" ], componentID );
  }

  unsubscribe ( componentID ) {
    MiddlewareClient.unsubscribe( [ "network.changed" ], componentID );
    MiddlewareClient.unsubscribe( [ "task.*" ], componentID );
  }

  requestNetworkConfig () {
    MiddlewareClient.request( "task.submit"
                              , [ "network.config.get_global_config" ]
                              , requestNetworkConfigCallback
                            );
  }

  requestNetworkConfigCallback ( networkConfig ) {
    NetworkConfigActionCreators.receiveNetworkConfig( networkConfig );
  }

  updateNetworkConfig ( newNetworkConfig ) {
    MiddlewareClient.request( "task.submit"
                            , [ "network.configure" ]
                            , updateNetworkConfigCallback
                            );
  }

  updateNetworkConfigCallback ( taskID ) {
    NetworkConfigActionCreators.receiveNetworkUpdateTask( taskID );
  }

};

export default new NetworkConfigMiddleware ();
