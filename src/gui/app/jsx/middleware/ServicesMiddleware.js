// Services Middleware
// ===================

"use strict";

import MC from "./MiddlewareClient";
import AbstractBase from "./MiddlewareAbstract";

import SAC from "../actions/ServicesActionCreators";

class ServicesMiddleware extends AbstractBase {

  static subscribeToTask ( componentID ) {
    MC.subscribe( [ "task.*" ], componentID );
  }

  static unsubscribeFromTask ( componentID ) {
    MC.unsubscribe( [ "task.*" ], componentID );
  }

  static updateService ( serviceName, action ) {
    MC.request( "task.submit"
              , [ "service.manage", [ serviceName, action ] ]
              , function handleUpdateService ( taskID ) {
                  SAC.receiveServiceUpdateTask( taskID, serviceName );
                }
              );
  }

  static configureService ( serviceName, configArray ) {
    MC.request( "task.submit"
              , [ "service.configure", [ serviceName, configArray ] ]
              , function handleUpdateService ( taskID ) {
                  SAC.receiveServiceUpdateTask( taskID, serviceName );
                }
              );
  }

  static requestServicesList () {
    MC.request( "services.query"
              , []
              , function ( rawServicesList ) {
                  SAC.receiveServicesList( rawServicesList );
                }
              );
  }

};

export default ServicesMiddleware;
