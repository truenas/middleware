// Network Config Middleware
// =========================

"use strict";

import MC from "./MiddlewareClient";
import AbstractBase from "./MiddlewareAbstract";

import NCAC
  from "../actions/NetworkConfigActionCreators";

class NetworkConfigMiddleware {

  static subscribe ( componentID ) {
    MC.subscribe( [ "network.changed" ], componentID );
    MC.subscribe( [ "task.*" ], componentID );
  }

  static unsubscribe ( componentID ) {
    MC.unsubscribe( [ "network.changed" ], componentID );
    MC.unsubscribe( [ "task.*" ], componentID );
  }

  static requestNetworkConfig () {
    MC.request( "network.config.get_global_config"
              , []
              , NCAC.receiveNetworkConfig.bind( NCAC )
              );
  }

  static updateNetworkConfig ( settings ) {
    MC.request( "task.submit"
              , [ "network.configure", [ settings ] ]
              , NCAC.receiveNetworkUpdateTask.bind( NCAC )
              );
  }

};

export default NetworkConfigMiddleware;
