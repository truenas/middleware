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
      , currentUser
      , loggedIn
      }
    );
  }

  static updateSocketState ( sockState ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.UPDATE_SOCKET_STATE
      , sockState
      }
    );
  }

  static updateReconnectTime ( ETA ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.UPDATE_RECONNECT_TIME
      , ETA
      }
    );
  }

  static increaseSubscriptionCount ( mask ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.SUBSCRIBE_TO_MASK
      , mask
      }
    );
  }

  static decreaseSubscriptionCount ( mask ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.UNSUBSCRIBE_FROM_MASK
      , mask
      }
    );
  }

  static receiveEventData ( eventData ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.MIDDLEWARE_EVENT
      , eventData
      }
    );
  }

  static receiveAvailableServices ( services ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_RPC_SERVICES
      , services
      }
    );
  }

  static receiveAvailableServiceMethods ( service, methods ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_RPC_SERVICE_METHODS
      , service
      , methods
      }
    );
  }

};

export default MiddleWareActionCreators;
