// Middleware Action Creators
// ==================================
// Handle high level Middleware events and actions, handle lifecycle and
// authentication changes, and call the dispatcher

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class MiddleWareActionCreators {

  static receiveAuthenticationChange ( currentUser, loggedIn, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.UPDATE_AUTH_STATE
      , timestamp
      , currentUser
      , loggedIn
      }
    );
  }

  static updateSocketState ( sockState, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.UPDATE_SOCKET_STATE
      , timestamp
      , sockState
      }
    );
  }

  static updateReconnectTime ( ETA, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.UPDATE_RECONNECT_TIME
      , timestamp
      , ETA
      }
    );
  }

  static increaseSubscriptionCount ( mask, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.SUBSCRIBE_TO_MASK
      , timestamp
      , mask
      }
    );
  }

  static decreaseSubscriptionCount ( mask, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.UNSUBSCRIBE_FROM_MASK
      , timestamp
      , mask
      }
    );
  }

  static receiveEventData ( eventData, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.MIDDLEWARE_EVENT
      , timestamp
      , eventData
      }
    );
  }

  static receiveAvailableServices ( services, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_RPC_SERVICES
      , timestamp
      , services
      }
    );
  }

  static receiveAvailableServiceMethods ( service, methods, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_RPC_SERVICE_METHODS
      , timestamp
      , service
      , methods
      }
    );
  }

};

export default MiddleWareActionCreators;
