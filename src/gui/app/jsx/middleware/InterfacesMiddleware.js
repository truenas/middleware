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
                , function handleRequestInterfacesList ( rawInterfacesList ) {
                    IAC.receiveInterfacesList( rawInterfacesList );
                  }
                );
    }

  static configureInterface ( interfaceName, props ) {
    MC.request( "task.submit"
              , [ "network.interface.configure", [ interfaceName, props ] ]
              , function handleConfigureInterface ( taskID, interfaceName ) {
                  IAC.receiveInterfaceConfigureTask( taskID, interfaceName );
                }
              );
  }

  static upInterface ( interfaceName ) {
    MC.request( "task.submit"
              , [ "network.interface.up", [ interfaceName ] ]
              , function handleUpInterface ( taskID, interfaceName ) {
                  IAC.receiveUpInterfaceTask( taskID, interfaceName );
                }
              );
  }

  static downInterface ( interfaceName ) {
    MC.request( "task.submit"
              , [ "network.interface.down", [ interfaceName ] ]
              , function handleDownInterface ( taskID, interfaceName ) {
                  IAC.receiveDownInterfaceTask( taskID, interfaceName );
                }
              );
  }

};

export default InterfacesMiddleware;
