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

var _subscribed    = {};
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

  , getNumberOfSubscriptions: function( masks ) {
      return _subscribed[ masks ];
    }

});

MiddlewareStore.dispatchToken = FreeNASDispatcher.register( function( payload ) {
  var action = payload.action;

  switch( action.type ) {

    // Authentication
    case ActionTypes.UPDATE_AUTH_STATE:
      _authenticated = action.authState;
      MiddlewareStore.emitChange();
      break;


    // Subscriptions
    case ActionTypes.SUBSCRIBE_TO_MASK:
      if ( typeof _subscribed[ action.mask ] === "number" ) {
        _subscribed[ action.mask ]++;
      } else {
        _subscribed[ action.mask ] = 1;
      }

      MiddlewareStore.emitChange();
      break;

    case ActionTypes.UNSUBSCRIBE_FROM_MASK:
      if ( typeof _subscribed[ action.mask ] === "number" ) {
        if ( _subscribed[ action.mask ] === 1 ) {
          delete _subscribed[ action.mask ];
        } else {
          _subscribed[ action.mask ]--;
        }
      } else {
        console.warn( "Tried to unsubscribe from '" + action.mask + "', but Flux store shows no active subsctiptions.");
      }

      MiddlewareStore.emitChange();
      break;


    case ActionTypes.MIDDLEWARE_EVENT:

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
