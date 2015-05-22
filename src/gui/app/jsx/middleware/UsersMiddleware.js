// Users Middleware
// ================
// Handle the lifecycle and event hooks for the Users channel of the middleware

"use strict";

import MC from "./MiddlewareClient";
import AbstractBase from "./MiddlewareAbstract";

import UAC from "../actions/UsersActionCreators";

class UsersMiddleware extends AbstractBase {

  static subscribe ( componentID ) {
    MC.subscribe( [ "users.changed" ], componentID );
    MC.subscribe( [ "task.*" ], componentID );
  }

  static unsubscribe ( componentID ) {
    MC.unsubscribe( [ "users.changed" ], componentID );
    MC.unsubscribe( [ "task.*" ], componentID );
  }

  static requestUsersList ( ids ) {
    MC.request( "users.query"
              , ( ids
                ? [[[ "id", "in", ids ]]]
                : []
                )
              , function handleUsersList ( rawUsersList ) {
                  UAC.receiveUsersList( rawUsersList );
                }
              );
  }

  static createUser ( newUserProps ) {
    MC.request( "task.submit"
              , [ "users.create" , [ newUserProps ] ]
              , function handleCreateUser ( taskID, userID ) {
                  UAC.receiveUserUpdateTask( taskID, userID );
                }
              );
  }

  static updateUser ( userID, changedProps ) {
    MC.request( "task.submit"
              , [ "users.update", [ userID, changedProps ] ]
              , function handleUpdateUser ( taskID ) {
                  UAC.receiveUserUpdateTask( taskID, userID );
                }
              );
  }

  static deleteUser ( userID ) {
    MC.request( "task.submit"
              , [ "users.delete", [ userID ] ]
              , function handleDeleteUser ( taskID, userID ) {
                  UAC.receiveUserUpdateTask( taskID, userID );
                }
              );
  }

};

export default UsersMiddleware;
