// Middleware Action Creators
// ==================================
// Handle high level Middleware events and actions, handle lifecycle and
// authentication changes, and call the dispatcher

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class MiddleWareActionCreators {

  static receiveAuthenticationChange ( currentUser, loggedIn ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.UPDATE_AUTH_STATE
      , currentUser: currentUser
      , loggedIn: loggedIn
      }
    );
  }

  static updateSocketState ( sockState ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.UPDATE_SOCKET_STATE
      , sockState: sockState
      }
    );
  }

  static updateReconnectTime ( ETA ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.UPDATE_RECONNECT_TIME
      , ETA: ETA
      }
    );
  }

  static increaseSubscriptionCount ( mask ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.SUBSCRIBE_TO_MASK
      , mask: mask
      }
    );
  }

  static decreaseSubscriptionCount ( mask ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.UNSUBSCRIBE_FROM_MASK
      , mask: mask
      }
    );
  }

  static receiveEventData ( eventData ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.MIDDLEWARE_EVENT
      , eventData: eventData
      }
    );
  }

  static receiveAvailableServices ( services ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_RPC_SERVICES
      , services: services
      }
    );
  }

  static receiveAvailableServiceMethods ( service, methods ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_RPC_SERVICE_METHODS
      , service: service
      , methods: methods
      }
    );
  }

};

export default MiddleWareActionCreators;
