// Users Flux Store
// ----------------

"use strict";

var _            = require("lodash");
var EventEmitter = require("events").EventEmitter;

var FreeNASDispatcher = require("../dispatcher/FreeNASDispatcher");
var FreeNASConstants  = require("../constants/FreeNASConstants");

var ActionTypes  = FreeNASConstants.ActionTypes;
var CHANGE_EVENT = "change";

var _users = [];

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
      // FIXME: Probably want to do some additional processing here, perhaps
      // add some metadata?
      _users = action.rawUsers;
      UsersStore.emitChange();
      break;

    default:
      // No action
  }
});

module.exports = UsersStore;
