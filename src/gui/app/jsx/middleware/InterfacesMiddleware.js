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
                , IAC.receiveInterfacesList.bind( IAC )
                );
    }

  static configureInterface ( interfaceName, props ) {
    MC.request( "task.submit"
              , [ "network.interface.configure", [ interfaceName, props ] ]
              , IAC.receiveInterfaceConfigureTask.bind( IAC )
              );
  }

  static upInterface ( interfaceName ) {
    MC.request( "task.submit"
              , [ "network.interface.up", [ interfaceName ] ]
              , IAC.receiveUpInterfaceTask.bind( IAC )
              );
  }

  static downInterface ( interfaceName ) {
    MC.request( "task.submit"
              , [ "network.interface.down", [ interfaceName ] ]
              , IAC.receiveDownInterfaceTask.bind( IAC )
              );
  }

};

export default InterfacesMiddleware;
