// Tasks Flux Store
// ================
// Maintain log of tasks, and their respective status.

"use strict";

var _            = require("lodash");
var EventEmitter = require("events").EventEmitter;

var FreeNASDispatcher = require("../dispatcher/FreeNASDispatcher");
var FreeNASConstants  = require("../constants/FreeNASConstants");

var ActionTypes  = FreeNASConstants.ActionTypes;
var CHANGE_EVENT = "change";

var _created   = {};
var _waiting   = {};
var _executing = {};
var _finished  = {};

var TasksStore = _.assign( {}, EventEmitter.prototype, {

    emitChange: function( namespace ) {
      this.emit( CHANGE_EVENT, namespace );
    }

  , addChangeListener: function( callback ) {
      this.on( CHANGE_EVENT, callback );
    }

  , removeChangeListener: function( callback ) {
      this.removeListener( CHANGE_EVENT, callback );
    }

  , getAllTasks: function() {
      return {
          CREATED   : _created
        , WAITING   : _waiting
        , EXECUTING : _executing
        , FINISHED  : _finished
      };
    }

  , getCreatedTasks: function() {
      return _created;
    }

  , getWaitingTasks: function() {
      return _waiting;
    }

  , getExecutingTasks: function() {
      return _executing;
    }

  , getFinishedTasks: function() {
      return _finished;
    }

});

TasksStore.dispatchToken = FreeNASDispatcher.register( function( payload ) {

  var action = payload.action;

  switch( action.type ) {


    case ActionTypes.MIDDLEWARE_EVENT:
      if ( action.eventData.args["name"].indexOf("task.") !== -1 ) {
        var taskArgs = action.eventData.args.args;

        var CREATED   = _created[ taskArgs["id"] ]   || {};
        var WAITING   = _waiting[ taskArgs["id"] ]   || {};
        var EXECUTING = _executing[ taskArgs["id"] ] || {};

        switch ( action.eventData.args["name"] ) {
          case "task.created":
            _created[ taskArgs["id"] ] = taskArgs;
            break;

          case "task.updated":
            switch( taskArgs["state"] ) {

              case "WAITING":
                _waiting[ taskArgs["id"] ] =
                  _.merge( CREATED
                         , taskArgs );

                delete _created[ taskArgs["id"] ];
                break;

              case "EXECUTING":
                _executing[ taskArgs["id"] ] =
                  _.merge( CREATED
                         , WAITING
                         , taskArgs );

                delete _created[ taskArgs["id"] ];
                delete _waiting[ taskArgs["id"] ];
                break;

              case "FINISHED":
                _finished[ taskArgs["id"] ] =
                  _.merge( CREATED
                         , WAITING
                         , EXECUTING
                         , taskArgs
                         , { "percentage" : 100 } );

                delete _created[ taskArgs["id"] ];
                delete _waiting[ taskArgs["id"] ];
                delete _executing[ taskArgs["id"] ];
                break;
            }

            break;

          case "task.progress":
            if ( _waiting[ taskArgs["id"] ] ) {
              _waiting[ taskArgs["id"] ] = _.merge( WAITING, taskArgs );
            } else if ( _executing[ taskArgs["id"] ] ) {
              _executing[ taskArgs["id"] ] = _.merge( EXECUTING, taskArgs );
            }
            break;
        }

        TasksStore.emitChange();
      }
      break;

    default:
      // No action
  }
});

module.exports = TasksStore;
