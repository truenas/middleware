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

// WARNING: This is a dangerous way of handling dispatches. Because of the
// way the FreeNAS webapp handles subscriptions, nested routes, and component
// heirarchy, it's possible for one dispatch to indirectly trigger another as
// part of the same call stack. Enqueueing dispatches in this way causes all
// dispatches to wait for the previous call stack to finish, but may
// inadvertently allow cascading or endless dispatches. Be careful.

// See also: https://github.com/facebook/flux/issues/106

class FreeNASDispatcher extends Dispatcher {

  constructor () {
    super();

    this.dispatchQueue = async.queue(
      function ( payload, callback ) {
        // FIXME: There's a bad interaction between the Flux Dispatcher's
        // dispatch function, the ES6 transform done by babelify, and core-js'
        // support for Symbols. It's not clear what the solution is, but Safari
        // isn't working right now.
        this.dispatch( payload );

        if ( _.isFunction( callback ) ) {
          callback();
        }
      }.bind( this )
    );
  }

  handleMiddlewareAction ( action ) {
    this.dispatchQueue.push({
        source : PayloadSources["MIDDLEWARE_ACTION"]
      , action : action
    });
  }

  handleMiddlewareLifecycle ( action ) {
    this.dispatchQueue.push({
        source : PayloadSources["MIDDLEWARE_LIFECYCLE"]
      , action : action
    });
  }

  handleClientAction ( action ) {
    this.dispatchQueue.push({
        source : PayloadSources["CLIENT_ACTION"]
      , action : action
    });
  }

}

export default new FreeNASDispatcher();
