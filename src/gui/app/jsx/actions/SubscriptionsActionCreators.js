// Subscriptions Action Creators
// ==================================
// Handle recording and removing subscription data, as well as information about
// the views that are subscribing.

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

module.exports = {

    recordNewSubscriptions: function ( masks, componentID ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type        : ActionTypes.SUBSCRIBE_COMPONENT_TO_MASKS
        , masks       : masks
        , componentID : componentID
      });
    }

  , deleteCurrentSubscriptions: function ( masks, componentID ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type        : ActionTypes.UNSUBSCRIBE_COMPONENT_FROM_MASKS
        , masks       : masks
        , componentID : componentID
      });
    }

  , deleteAllSubscriptions: function () {
      FreeNASDispatcher.handleMiddlewareAction({
        type          : ActionTypes.UNSUBSCRIBE_ALL
      });
    }

};
