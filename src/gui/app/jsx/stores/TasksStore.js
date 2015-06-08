// Tasks Flux Store
// ================
// Maintain log of tasks, and their respective status.

"use strict";

import _ from "lodash";
import { EventEmitter } from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

var CHANGE_EVENT = "change";

var _created   = {};
var _waiting   = {};
var _executing = {};
var _finished  = {};
var _failed    = {};
var _aborted   = {};

var TasksStore = _.assign( {}, EventEmitter.prototype
  , { emitChange: function ( namespace ) {
        this.emit( CHANGE_EVENT, namespace );
      }

    , addChangeListener: function ( callback ) {
        this.on( CHANGE_EVENT, callback );
      }

    , removeChangeListener: function ( callback ) {
        this.removeListener( CHANGE_EVENT, callback );
      }

    , getAllTasks: function () {
        return { CREATED   : _created
               , WAITING   : _waiting
               , EXECUTING : _executing
               , FINISHED  : _finished
               , FAILED    : _failed
               , ABORTED   : _aborted
        };
      }

    , getCreatedTasks: function () {
        return _created;
      }

    , getWaitingTasks: function () {
        return _waiting;
      }

    , getExecutingTasks: function () {
        return _executing;
      }

    , getFinishedTasks: function () {
        return _finished;
      }

    , getFailedTasks: function () {
        return _failed;
      }

    , getAbortedTasks: function () {
        return _aborted;
      }
    }
);

TasksStore.dispatchToken = FreeNASDispatcher.register( function ( payload ) {

  var action = payload.action;

  switch ( action.type ) {


    case ActionTypes.MIDDLEWARE_EVENT:
      if ( action.eventData.args["name"].indexOf( "task." ) !== -1 ) {
        var taskArgs = action.eventData.args.args;
        var CREATED   = _created[ taskArgs["id"] ]   || {};
        var WAITING   = _waiting[ taskArgs["id"] ]   || {};
        var EXECUTING = _executing[ taskArgs["id"] ] || {};

        switch ( action.eventData.args[ "name" ] ) {
          case "task.created":
            _created[ taskArgs[ "id" ] ] = taskArgs;
            break;

          case "task.updated":
            switch ( taskArgs[ "state" ] ) {

              case "WAITING":
                _waiting[ taskArgs[ "id" ] ] =
                  _.merge( CREATED
                         , taskArgs );

                delete _created[ taskArgs[ "id" ] ];
                break;

              case "EXECUTING":
                _executing[ taskArgs[ "id" ] ] =
                  _.merge( CREATED
                         , WAITING
                         , taskArgs );

                delete _created[ taskArgs[ "id" ] ];
                delete _waiting[ taskArgs[ "id" ] ];
                break;

              case "FINISHED":
                _finished[ taskArgs[ "id" ] ] =
                  _.merge( CREATED
                         , WAITING
                         , EXECUTING
                         , taskArgs
                         , { percentage: 100 } );

                delete _created[ taskArgs[ "id" ] ];
                delete _waiting[ taskArgs[ "id" ] ];
                delete _executing[ taskArgs[ "id" ] ];
                break;

              case "ABORTED":
                _aborted[ taskArgs["id"] ] =
                  _.merge( CREATED
                         , WAITING
                         , EXECUTING
                         , taskArgs
                         , { percentage: taskArgs[ "percentage" ] } );
                delete _created[ taskArgs["id"] ];
                delete _waiting[ taskArgs["id"] ];
                delete _executing[ taskArgs["id"] ];
                break;

              case "FAILED":
                _failed[ taskArgs["id"] ] =
                  _.merge( CREATED
                         , WAITING
                         , EXECUTING
                         , taskArgs
                         , { percentage: taskArgs[ "percentage" ] } );
                delete _created[ taskArgs["id"] ];
                delete _waiting[ taskArgs["id"] ];
                delete _executing[ taskArgs["id"] ];
                break;
            }

            break;

          case "task.progress":
            switch ( taskArgs[ "state" ] ){
              case "WAITING":
                _waiting[ taskArgs[ "id" ] ] = _.merge( WAITING, taskArgs );
                break;

              case "EXECUTING":
                _executing[ taskArgs[ "id" ] ] = _.merge( EXECUTING, taskArgs );
                break;

              case "FAILED":
                let perct = taskArgs[ "percentage" ] === 0 ? 50 :
                              taskArgs[ "percentage" ];
                _failed[ taskArgs["id"] ] =
                  _.merge( CREATED
                         , WAITING
                         , EXECUTING
                         , taskArgs
                         , { percentage: perct } );
                delete _created[ taskArgs["id"] ];
                delete _waiting[ taskArgs["id"] ];
                delete _executing[ taskArgs["id"] ];
                break;

              case "ABORTED":
                let perct = taskArgs[ "percentage" ] === 0 ? 50 :
                              taskArgs[ "percentage" ];
                _aborted[ taskArgs["id"] ] =
                  _.merge( CREATED
                         , WAITING
                         , EXECUTING
                         , taskArgs
                         , { percentage: perct } );
                delete _created[ taskArgs["id"] ];
                delete _waiting[ taskArgs["id"] ];
                delete _executing[ taskArgs["id"] ];
                break;
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
