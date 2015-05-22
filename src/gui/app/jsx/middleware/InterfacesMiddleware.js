// Interfaces Middleware
// =====================

"use strict";

import MC from "./MiddlewareClient";
import AbstractBase from "./MiddlewareAbstract";

import IAC from "../actions/InterfacesActionCreators";

class InterfacesMiddleware extends AbstractBase {

  static subscribe ( componentID ) {
    MC.subscribe( [ "networks.changed" ], componentID );
    MC.subscribe( [ "task.*" ], componentID );
  }

  static unsubscribe ( componentID ) {
    MC.unsubscribe( [ "networks.changed" ], componentID );
    MC.unsubscribe( [ "task.*" ], componentID );
  }

  static requestInterfacesList () {
      MC.request( "network.interfaces.query"
                , []
                , function handleRequestInterfacesList ( rawInterfacesList ) {
                    IAC.receiveInterfacesList( rawInterfacesList );
                  }
                );
    }

};

export default InterfacesMiddleware;
