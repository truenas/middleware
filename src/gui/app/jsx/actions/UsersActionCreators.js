// Users Action Creators
// ==================================
// Receive and handle events from the middleware, and call the dispatcher.

"use strict";

var FreeNASDispatcher = require("../dispatcher/FreeNASDispatcher");
var FreeNASConstants  = require("../constants/FreeNASConstants");

var ActionTypes = FreeNASConstants.ActionTypes;

module.exports = {

    receiveUsersList: function( rawUsers ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type     : ActionTypes.RECEIVE_RAW_USERS
        , rawUsers : rawUsers
      });
    }

  , receiveChangedIDs: function( changedIDs ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type       : ActionTypes.RECEIVE_CHANGED_USER_IDS
        , changedIDs : changedIDs
      });
    }

};
