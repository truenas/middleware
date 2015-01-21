// Users Flux Store
// ----------------

"use strict";

var _            = require("lodash");
var EventEmitter = require("events").EventEmitter;

var FreeNASDispatcher = require("../dispatcher/FreeNASDispatcher");
var FreeNASConstants  = require("../constants/FreeNASConstants");

var ActionTypes  = FreeNASConstants.ActionTypes;
var CHANGE_EVENT = "change";

var _updatedOnServer = [];
var _users           = [];

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
        _updatedOnServer = _.without( _updatedOnServer, _.pluck( action.rawUsers, "username" ) );
      }

      _users = action.rawUsers;
      UsersStore.emitChange();
      break;

    case ActionTypes.RECEIVE_CHANGED_USER_IDS:
      _updatedOnServer.push( payload.changedIDs );
      break;

    default:
      // No action
  }
});

module.exports = UsersStore;
