// Groups Action Creators
// ==================================
// Receive and handle events from the middleware, and call the dispatcher.

"use strict";

var FreeNASDispatcher = require("../dispatcher/FreeNASDispatcher");
var FreeNASConstants  = require("../constants/FreeNASConstants");

var ActionTypes = FreeNASConstants.ActionTypes;

module.exports = {

    receiveGroupsList: function( groupsList ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type         : ActionTypes.RECEIVE_GROUPS_LIST
        , groupsList : groupsList
      });
    }

  , receiveGroupUpdateTask: function( taskID, groupID) {
      FreeNASDispatcher.handleMiddlewareAction({
          type    : ActionTypes.RECEIVE_GROUP_UPDATE_TASK
        , taskID  : taskID
        , groupID : groupID
      });
    }

};
