// Users Flux Store
// ----------------

"use strict";

var _            = require("lodash");
var EventEmitter = require("events").EventEmitter;

var FreeNASDispatcher = require("../dispatcher/FreeNASDispatcher");
var FreeNASConstants  = require("../constants/FreeNASConstants");

var UsersMiddleware = require("../middleware/UsersMiddleware");

var ActionTypes  = FreeNASConstants.ActionTypes;
var CHANGE_EVENT = "change";
var UPDATE_MASK  = "users.changed";

var _updatedOnServer    = [];
var _localUpdatePending = {};
var _users              = [];

var UsersStore = _.assign( {}, EventEmitter.prototype, {

    emitChange: function() {
      this.emit( CHANGE_EVENT );
    }

  , addChangeListener: function( callback ) {
      this.on( CHANGE_EVENT, callback );
    }

  , removeChangeListener: function( callback ) {
      this.removeListener( CHANGE_EVENT, callback );
    }

  , getUpdateMask: function() {
      return UPDATE_MASK;
    }

  , getUser: function( key ) {
      // FIXME: Placeholder, won't work as [{}] is unkeyed from middleware.
      return _users[ key ];
    }

  , getAllUsers: function() {
      return _users;
    }

});

UsersStore.dispatchToken = FreeNASDispatcher.register( function( payload ) {
  var action = payload.action;

  switch( action.type ) {

    case ActionTypes.RECEIVE_RAW_USERS:

      // When receiving new data, we can comfortably resolve anything that may
      // have had an outstanding update indicated by the Middleware.
      if ( _updatedOnServer.length > 0 ) {
        _updatedOnServer = _.difference( _updatedOnServer, _.pluck( action.rawUsers, "id" ) );
      }

      _users = action.rawUsers;
      UsersStore.emitChange();
      break;

    case ActionTypes.MIDDLEWARE_EVENT:
      console.log( action.eventData );
      if ( action.eventData.args["name"] === UPDATE_MASK ) {
        var updateData = action.eventData.args["args"];

        if ( updateData["operation"] === "update" ) {
          Array.prototype.push.apply( _updatedOnServer, updateData["ids"] );
          // FIXME: This is a workaround for the current implementation of task
          // subscriptions and submission resolutions.
          UsersMiddleware.requestUsersList();
          // UsersMiddleware.requestUsersList( _updatedOnServer );
        } else {
          // TODO: Can this be anything else?
        }
      }
      break;

    case ActionTypes.RECEIVE_USER_UPDATE_TASK:
      _localUpdatePending[ action.taskID ] = action.userID;
      UsersStore.emitChange();
      break;

    case ActionTypes.RESOLVE_USER_UPDATE_TASK:
      delete _localUpdatePending[ action.taskID ];
      UsersStore.emitChange();
      break;


    default:
      // No action
  }
});

module.exports = UsersStore;
