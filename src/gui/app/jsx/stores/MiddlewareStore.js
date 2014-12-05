// Middleware Flux Store
// =====================
// Maintain consistent information about the general state of the middleware
// client, including which channels are connected, pending calls, authentication
// status, and blocked operations.

"use strict";

var _            = require("lodash");
var EventEmitter = require("events").EventEmitter;

var FreeNASDispatcher = require("../dispatcher/FreeNASDispatcher");
var FreeNASConstants  = require("../constants/FreeNASConstants");

var ActionTypes  = FreeNASConstants.ActionTypes;
var CHANGE_EVENT = "change";

var _subscribed    = [];
var _events        = {};
var _authenticated = false;


var MiddlewareStore = _.assign( {}, EventEmitter.prototype, {

    emitChange: function() {
      this.emit( CHANGE_EVENT );
    }

  , addChangeListener: function( callback ) {
      this.on( CHANGE_EVENT, callback );
    }

  , removeChangeListener: function( callback ) {
      this.removeListener( CHANGE_EVENT, callback );
    }

  , getAuthStatus: function() {
      return _authenticated;
    }

});

MiddlewareStore.dispatchToken = FreeNASDispatcher.register( function( payload ) {
  var action = payload.action;

  switch( action.type ) {

    case ActionTypes.UPDATE_AUTH_STATE:
      _authenticated = action.authState;
      MiddlewareStore.emitChange();
      break;

    case ActionTypes.LOG_MIDDLEWARE_EVENT:

      // TODO: handle events

      MiddlewareStore.emitChange();
      break;

    case ActionTypes.LOG_MIDDLEWARE_TASK_QUEUE:

      // TODO: handle task queue

      MiddlewareStore.emitChange();
      break;

    default:
      // No action
  }
});

module.exports = MiddlewareStore;
