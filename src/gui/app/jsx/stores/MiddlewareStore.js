// Middleware Flux Store
// =====================
// Maintain consistent information about the general state of the middleware
// client, including which channels are connected, pending calls, and blocked operations.

"use strict";

var _            = require("lodash");
var EventEmitter = require("events").EventEmitter;

var FreeNASDispatcher = require("../dispatcher/FreeNASDispatcher");
var FreeNASConstants  = require("../constants/FreeNASConstants");

var ActionTypes  = FreeNASConstants.ActionTypes;
var CHANGE_EVENT = "change";

var _subscribed    = {};
var _rpcServices   = [];
var _rpcMethods    = {};
var _events        = [];
var _stats         = {};
var _tasks = {
    CREATED   : {}
  , WAITING   : {}
  , EXECUTING : {}
  , FINISHED  : {}
};


var MiddlewareStore = _.assign( {}, EventEmitter.prototype, {

    emitChange: function( namespace ) {
      this.emit( CHANGE_EVENT, namespace );
    }

  , addChangeListener: function( callback ) {
      this.on( CHANGE_EVENT, callback );
    }

  , removeChangeListener: function( callback ) {
      this.removeListener( CHANGE_EVENT, callback );
    }

  // SUBSCRIPTIONS
  , getAllSubscriptions: function() {
      return _subscribed;
    }

  , getNumberOfSubscriptions: function( masks ) {
      return _subscribed[ masks ];
    }

  // RPC
  , getAvailableRPCServices: function() {
      return _rpcServices;
    }

  , getAvailableRPCMethods: function() {
      return _rpcMethods;
    }

  // EVENTS
  , getEventLog: function() {
      return _events;
    }

  // TASKS
  , getAllTasks: function() {
      return _tasks;
    }

  , getCreatedTasks: function() {
      return _tasks["CREATED"];
    }

  , getWaitingTasks: function() {
      return _tasks["WAITING"];
    }

  , getExecutingTasks: function() {
      return _tasks["EXECUTING"];
    }

  , getFinishedTasks: function() {
      return _tasks["FINISHED"];
    }

});

MiddlewareStore.dispatchToken = FreeNASDispatcher.register( function( payload ) {
  var action = payload.action;

  switch( action.type ) {

    // Subscriptions
    case ActionTypes.SUBSCRIBE_TO_MASK:
      if ( typeof _subscribed[ action.mask ] === "number" ) {
        _subscribed[ action.mask ]++;
      } else {
        _subscribed[ action.mask ] = 1;
      }

      MiddlewareStore.emitChange("subscriptions");
      break;

    case ActionTypes.UNSUBSCRIBE_FROM_MASK:
      if ( typeof _subscribed[ action.mask ] === "number" ) {
        if ( _subscribed[ action.mask ] === 1 ) {
          delete _subscribed[ action.mask ];
        } else {
          _subscribed[ action.mask ]--;
        }
      } else {
        console.warn( "Tried to unsubscribe from '" + action.mask + "', but Flux store shows no active subscriptions.");
      }

      MiddlewareStore.emitChange("subscriptions");
      break;


    case ActionTypes.MIDDLEWARE_EVENT:

      // Prepend latest event to the front of the array
      _events.unshift( action.eventData );

      if ( action.eventData.args["name"].indexOf("task.") !== -1 ) {
        var taskArgs = action.eventData.args.args;

        var CREATED   = _tasks["CREATED"][ taskArgs["id"] ]   || {};
        var WAITING   = _tasks["WAITING"][ taskArgs["id"] ]   || {};
        var EXECUTING = _tasks["EXECUTING"][ taskArgs["id"] ] || {};

        switch ( action.eventData.args["name"] ) {
          case "task.created":
            _tasks["CREATED"][ taskArgs["id"] ] = taskArgs;
            break;

          case "task.updated":
            switch( taskArgs["state"] ) {

              case "WAITING":
                _tasks["WAITING"][ taskArgs["id"] ] =
                  _.merge( CREATED
                         , taskArgs );

                delete _tasks["CREATED"][ taskArgs["id"] ];
                break;

              case "EXECUTING":
                _tasks["EXECUTING"][ taskArgs["id"] ] =
                  _.merge( CREATED
                         , WAITING
                         , taskArgs );

                delete _tasks["CREATED"][ taskArgs["id"] ];
                delete _tasks["WAITING"][ taskArgs["id"] ];
                break;

              case "FINISHED":
                _tasks["FINISHED"][ taskArgs["id"] ] =
                  _.merge( CREATED
                         , WAITING
                         , EXECUTING
                         , taskArgs
                         , { "percentage" : 100 } );

                delete _tasks["CREATED"][ taskArgs["id"] ];
                delete _tasks["WAITING"][ taskArgs["id"] ];
                delete _tasks["EXECUTING"][ taskArgs["id"] ];
                break;
            }

            break;

          case "task.progress":
            if ( _tasks["WAITING"][ taskArgs["id"] ] ) {
              _tasks["WAITING"][ taskArgs["id"] ] = _.merge( WAITING, taskArgs );
            } else if ( _tasks["EXECUTING"][ taskArgs["id"] ] ) {
              _tasks["EXECUTING"][ taskArgs["id"] ] = _.merge( EXECUTING, taskArgs );
            }
            break;
        }

        MiddlewareStore.emitChange("tasks");
      } else {
        MiddlewareStore.emitChange("events");
      }

      break;

    case ActionTypes.LOG_MIDDLEWARE_TASK_QUEUE:

      // TODO: handle task queue

      MiddlewareStore.emitChange();
      break;

    case ActionTypes.RECEIVE_RPC_SERVICES:
      _rpcServices = action.services;

      MiddlewareStore.emitChange("services");
      break;

    case ActionTypes.RECEIVE_RPC_SERVICE_METHODS:
      _rpcMethods[ action.service ] = action.methods;

      MiddlewareStore.emitChange("methods");
      break;



    default:
      // No action
  }
});

module.exports = MiddlewareStore;
