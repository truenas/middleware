// Subscriptions Action Creators
// ==================================
// Handle recording and removing subscription data, as well as information about
// the views that are subscribing.

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class SubscriptionsActionCreators {

  static recordNewSubscriptions ( masks, componentID, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.SUBSCRIBE_COMPONENT_TO_MASKS
      , timestamp
      , masks
      , componentID
      }
    );
  }

  static deleteCurrentSubscriptions ( masks, componentID, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.UNSUBSCRIBE_COMPONENT_FROM_MASKS
      , timestamp
      , masks
      , componentID
      }
    );
  }

  static deleteAllSubscriptions ( timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.UNSUBSCRIBE_ALL
      , timestamp
      }
    );
  }

};

export default SubscriptionsActionCreators;
