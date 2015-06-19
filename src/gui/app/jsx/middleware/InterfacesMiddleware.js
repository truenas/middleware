// Interfaces Middleware
// =====================

"use strict";

import MC from "./MiddlewareClient";
import AbstractBase from "./MiddlewareAbstract";

import IAC from "../actions/InterfacesActionCreators";

class InterfacesMiddleware extends AbstractBase {

  static subscribe ( componentID ) {
    MC.subscribe( [ "network.interface.*" ], componentID );
    MC.subscribe( [ "task.*" ], componentID );
  }

  static unsubscribe ( componentID ) {
    MC.unsubscribe( [ "network.interface.*" ], componentID );
    MC.unsubscribe( [ "task.*" ], componentID );
  }

  static requestInterfacesList () {
      MC.request( "network.interfaces.query"
                , []
                , IAC.receiveInterfacesList
                );
    }

  static configureInterface ( interfaceName, props ) {
    MC.request( "task.submit"
              , [ "network.interface.configure", [ interfaceName, props ] ]
              , IAC.receiveInterfaceConfigureTask.bind( IAC, interfaceName )
              );
  }

  static upInterface ( interfaceName ) {
    MC.request( "task.submit"
              , [ "network.interface.up", [ interfaceName ] ]
              , IAC.receiveUpInterfaceTask.bind( IAC, interfaceName )
              );
  }

  static downInterface ( interfaceName ) {
    MC.request( "task.submit"
              , [ "network.interface.down", [ interfaceName ] ]
              , IAC.receiveDownInterfaceTask.bind( IAC, interfaceName )
              );
  }

};

export default InterfacesMiddleware;
