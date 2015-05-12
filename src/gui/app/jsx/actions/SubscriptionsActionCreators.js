// Subscriptions Action Creators
// ==================================
// Handle recording and removing subscription data, as well as information about
// the views that are subscribing.

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class SubscriptionsActionCreators {

  recordNewSubscriptions ( masks, componentID ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.SUBSCRIBE_COMPONENT_TO_MASKS
      , masks: masks
      , componentID: componentID
      }
    );
  }

  deleteCurrentSubscriptions ( masks, componentID ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.UNSUBSCRIBE_COMPONENT_FROM_MASKS
      , masks: masks
      , componentID: componentID
      }
    );
  }

  deleteAllSubscriptions () {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.UNSUBSCRIBE_ALL
      }
    );
  }

};

export default new SubscriptionsActionCreators();
