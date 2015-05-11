// Users Middleware
// ================
// Handle the lifecycle and event hooks for the Users channel of the middleware

"use strict";

import MiddlewareClient from "../middleware/MiddlewareClient";

import UsersActionCreators from "../actions/UsersActionCreators";

module.exports = {

  subscribe: function ( componentID ) {
      MiddlewareClient.subscribe( [ "users.changed" ], componentID );
      MiddlewareClient.subscribe( [ "task.*" ], componentID );
    }

  , unsubscribe: function ( componentID ) {
      MiddlewareClient.unsubscribe( [ "users.changed" ], componentID );
      MiddlewareClient.unsubscribe( [ "task.*" ], componentID );
    }

  , requestUsersList: function ( ids ) {
      MiddlewareClient.request( "users.query"
                              , ( ids ? [[[ "id", "in", ids ]]] : [] )
                              , function ( rawUsersList ) {
        UsersActionCreators.receiveUsersList( rawUsersList );
      });
    }

  , createUser: function ( newUserProps ) {
      MiddlewareClient.request( "task.submit"
                              , [ "users.create" , [ newUserProps ] ]
                              , function ( taskID, userID ) {
        UsersActionCreators.receiveUserUpdateTask( taskID, userID );
      });
    }

  , updateUser: function ( userID, changedProps ) {
      MiddlewareClient.request( "task.submit"
                              , [ "users.update", [ userID, changedProps ] ]
                              , function ( taskID ) {
        UsersActionCreators.receiveUserUpdateTask( taskID, userID );
      });
    }

  , deleteUser: function ( userID ) {
      MiddlewareClient.request( "task.submit"
                              , [ "users.delete", [ userID ] ]
                              , function ( taskID, userID ) {
        UsersActionCreators.receiveUserUpdateTask( taskID, userID );
      });
    }

};
