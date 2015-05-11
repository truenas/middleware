// Users Action Creators
// ==================================
// Receive and handle events from the middleware, and call the dispatcher.

"use strict";

var FreeNASDispatcher = require( "../dispatcher/FreeNASDispatcher" );
var FreeNASConstants  = require( "../constants/FreeNASConstants" );

var ActionTypes = FreeNASConstants.ActionTypes;

module.exports = {

  receiveUsersList: function ( rawUsers ) {
      FreeNASDispatcher.handleMiddlewareAction({
        type     : ActionTypes.RECEIVE_RAW_USERS
        , rawUsers : rawUsers
      });
    }

  , receiveUserUpdateTask: function ( taskID, userID ) {
      FreeNASDispatcher.handleClientAction({
        type   : ActionTypes.RECEIVE_USER_UPDATE_TASK
        , taskID : taskID
        , userID : userID
      });
    }

};
