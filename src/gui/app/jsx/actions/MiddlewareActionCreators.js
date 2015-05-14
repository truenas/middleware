// Middleware Action Creators
// ==================================
// Handle high level Middleware events and actions, handle lifecycle and
// authentication changes, and call the dispatcher

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class MiddleWareActionCreators {

  receiveAuthenticationChange ( currentUser, loggedIn ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.UPDATE_AUTH_STATE
      , currentUser: currentUser
      , loggedIn: loggedIn
      }
    );
  }

  updateSocketState ( sockState ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.UPDATE_SOCKET_STATE
      , sockState: sockState
      }
    );
  }

  increaseSubscriptionCount ( mask ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.SUBSCRIBE_TO_MASK
      , mask: mask
      }
    );
  }

  decreaseSubscriptionCount ( mask ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.UNSUBSCRIBE_FROM_MASK
      , mask: mask
      }
    );
  }

  receiveEventData ( eventData ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.MIDDLEWARE_EVENT
      , eventData: eventData
      }
    );
  }

  receiveAvailableServices ( services ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_RPC_SERVICES
      , services: services
      }
    );
  }

  receiveAvailableServiceMethods ( service, methods ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_RPC_SERVICE_METHODS
      , service: service
      , methods: methods
      }
    );
  }

};

export default new MiddleWareActionCreators();
