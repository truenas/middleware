// FreeNAS Dispatcher
// ------------------
// Flux dispatcher used throughout the FreeNAS webapp. Manages all data flow,
// updates data stores with new data from user interaction or from the
// middleware.

"use strict";

import _ from "lodash";
import async from "async";

import { Dispatcher } from "flux";

import { PayloadSources } from "../constants/FreeNASConstants";

var dispatchQueue;
var FreeNASDispatcher;


// WARNING: This is a dangerous way of handling dispatches. Because of the
// way the FreeNAS webapp handles subscriptions, nested routes, and component
// heirarchy, it's possible for one dispatch to indirectly trigger another as
// part of the same call stack. Enqueueing dispatches in this way causes all
// dispatches to wait for the previous call stack to finish, but may
// inadvertently allow cascading or endless dispatches. Be careful.

// See also: https://github.com/facebook/flux/issues/106

dispatchQueue = async.queue( function ( payload, callback ) {
  FreeNASDispatcher.dispatch( payload );

  if ( _.isFunction( callback ) ) { callback(); }
});

FreeNASDispatcher = _.assign( new Dispatcher(), {

    handleMiddlewareAction: function( action ) {
      dispatchQueue.push({
          source : PayloadSources["MIDDLEWARE_ACTION"]
        , action : action
      });
    }

  , handleMiddlewareLifecycle: function( action ) {
      dispatchQueue.push({
          source : PayloadSources["MIDDLEWARE_LIFECYCLE"]
        , action : action
      });
    }

  , handleClientAction: function( action ) {
      dispatchQueue.push({
          source : PayloadSources["CLIENT_ACTION"]
        , action : action
      });
    }

});

module.exports = FreeNASDispatcher;
