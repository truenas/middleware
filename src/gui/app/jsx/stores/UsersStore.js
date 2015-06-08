// Users Flux Store
// ----------------

"use strict";

import _ from "lodash";
import { EventEmitter } from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

import UsersMiddleware from "../middleware/UsersMiddleware";

var CHANGE_EVENT = "change";
var UPDATE_MASK  = "users.changed";
var PRIMARY_KEY  = "id";

var _updatedOnServer    = [];
var _localUpdatePending = {};
var _users              = {};

const USER_SCHEMA =
  { type: "object"
  , properties:
    { username:          { type: "string" }
    , sshpubkey:         { type: [ "string", "null" ] }
    , shell:             { type: "string" }
    , locked:            { type: "boolean" }
    , full_name:         { type: [ "string", "null" ] }
    , home:              { type: "string" }
    , group:             { type: "integer" }
    , id:                { type: "number" }
    , password_disabled: { type: "boolean" }
    , unixhash:          { type: [ "string", "null" ] }
    , sudo:              { type: "boolean" }
    , smbhash:           { type: [ "string", "null" ] }
    , email:             { type: [ "string", "null" ] }
    , groups:
      { items: { type: "integer" }
      , type: "array"
      }
    , sessions:
      { readOnly: true
      , type: "array"
      }
    , builtin:
      { readOnly: true
      , type: "boolean"
      }
    , loggedin:
      { readOnly: true
      , type: "boolean"
      }
  }
};

const USER_LABELS =
    { username          : "Username"
    , sshpubkey         : "SSH Public Key"
    , shell             : "Shell"
    , locked            : "Locked Account"
    , groups            : "Group Membership"
    , sessions          : "Sessions"
    , unixhash          : "UNIX Hash"
    , sudo              : "sudo Access"
    , smbhash           : "SMB Hash"
    , email             : "email Address"
    , builtin           : "Built-In User"
    , loggedin          : "Online"
    , full_name         : "Full Name"
    , home              : "Home Directory"
    , group             : "Primary Group"
    , id                : "User ID"
    , password_disabled : "Password Disabled"
  };

var UsersStore = _.assign( {}, EventEmitter.prototype, {

    emitChange: function () {
      this.emit( CHANGE_EVENT );
    }

  , addChangeListener: function( callback ) {
      this.on( CHANGE_EVENT, callback );
    }

  , removeChangeListener: function( callback ) {
      this.removeListener( CHANGE_EVENT, callback );
    }

  , getUpdateMask: function () {
      return UPDATE_MASK;
    }

  , getPendingUpdateIDs: function () {
      return _updatedOnServer;
    }

  , isLocalTaskPending: function( id ) {
      return _.values( _localUpdatePending ).indexOf( id ) > -1;
    }

  , isUserUpdatePending: function( id ) {
      return _updatedOnServer.indexOf( id ) > -1;
    }

  , findUserByKeyValue: function ( key, value ) {
      var predicate = {};
          predicate[key] = value;

      return _.find( _users, predicate );
    }

  , getUserSchema: function () {
      return USER_SCHEMA;
    }

  , getUserLabels: function () {
      return USER_LABELS;
    }

  , getUser: function( id ) {
      return _users[ id ];
    }

  , getAllUsers: function () {
      return _.values( _users );
    }

// Returns an array of the complete objects for each user in
// the requested group.
  , getUsersByGroup: function(groupID) {
      var groupUsers = _.filter( _users, function ( currentUser ) {
        if (_.includes(currentUser.groups, groupID) || currentUser.group === groupID){
          return true;
        } else {
          return false;
        }
      });
      return groupUsers;
  }

});

UsersStore.dispatchToken = FreeNASDispatcher.register( function( payload ) {
  var action = payload.action;

  switch( action.type ) {

    case ActionTypes.RECEIVE_RAW_USERS:

      var updatedUserIDs = _.pluck( action.rawUsers, PRIMARY_KEY );

      // When receiving new data, we can comfortably resolve anything that may
      // have had an outstanding update indicated by the Middleware.
      if ( _updatedOnServer.length > 0 ) {
        _updatedOnServer = _.difference( _updatedOnServer, updatedUserIDs );
      }

      action.rawUsers.map( function ( user ) {
          _users[ user [ PRIMARY_KEY ] ] = user;
      });

      UsersStore.emitChange();
      break;

    case ActionTypes.MIDDLEWARE_EVENT:
      var args = action.eventData.args;
      var updateData = args[ "args" ];

      // FIXME: This is a workaround for the current implementation of task
      // subscriptions and submission resolutions.
      if ( args[ "name" ] === UPDATE_MASK ) {
        if ( updateData[ "operation" ] === "delete" ) {
            // FIXME: Will this cause an issue if the delete is unsuccessful?
            // This will no doubt be overriden in the new patch-based world anyway.
            _users = _.omit(_users, updateData["ids"] );
        } else if ( updateData[ "operation" ] === "update" || updateData[ "operation" ] === "create" ) {
            Array.prototype.push.apply( _updatedOnServer, updateData["ids"] );
            UsersMiddleware.requestUsersList( _updatedOnServer );
        } else {
          // TODO: Are there any other cases?
        }
        UsersStore.emitChange();

      // TODO: Make this more generic, triage it earlier, create ActionTypes for it
      } else if ( args[ "name" ] === "task.updated" && args.args["state"] === "FINISHED" ) {
          delete _localUpdatePending[ args.args["id"] ];
      }

      break;

    case ActionTypes.RECEIVE_USER_UPDATE_TASK:
      _localUpdatePending[ action.taskID ] = action.userID;
      UsersStore.emitChange();
      break;

    default:
      // No action
  }
});

module.exports = UsersStore;
