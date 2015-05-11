// Middleware Action Creators
// ==================================
// Handle high level Middleware events and actions, handle lifecycle and
// authentication changes, and call the dispatcher

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

module.exports = {

    receiveAuthenticationChange: function ( currentUser, loggedIn ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type        : ActionTypes.UPDATE_AUTH_STATE
        , currentUser : currentUser
        , loggedIn    : loggedIn
      });
    }

  , updateSocketState: function ( sockState ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type      : ActionTypes.UPDATE_SOCKET_STATE
        , sockState : sockState
      });
    }

  , increaseSubscriptionCount: function ( mask ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type : ActionTypes.SUBSCRIBE_TO_MASK
        , mask : mask
      });
    }

  , decreaseSubscriptionCount: function ( mask ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type : ActionTypes.UNSUBSCRIBE_FROM_MASK
        , mask : mask
      });
    }

  , receiveEventData: function ( eventData ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type      : ActionTypes.MIDDLEWARE_EVENT
        , eventData : eventData
      });
    }

  , receiveAvailableServices: function ( services ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type     : ActionTypes.RECEIVE_RPC_SERVICES
        , services : services
      });
    }

  , receiveAvailableServiceMethods: function ( service, methods ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type    : ActionTypes.RECEIVE_RPC_SERVICE_METHODS
        , service : service
        , methods : methods
      });
    }

};
