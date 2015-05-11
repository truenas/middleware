// Groups Flux Store
// -----------------

"use strict";

import _ from "lodash";
import { EventEmitter } from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

import GroupsMiddleware from "../middleware/GroupsMiddleware";

var CHANGE_EVENT = "change";
var UPDATE_MASK  = "groups.changed";
var PRIMARY_KEY  = "id";

var _localUpdatePending = {};
var _updatedOnServer    = [];
var _groups = {};

var GroupsStore = _.assign( {}, EventEmitter.prototype, {

  emitChange: function () {
      this.emit( CHANGE_EVENT );
    }

  , addChangeListener: function ( callback ) {
      this.on( CHANGE_EVENT, callback );
    }

  , removeChangeListener: function ( callback ) {
      this.removeListener( CHANGE_EVENT, callback );
    }

  , getUpdateMask: function () {
      return UPDATE_MASK;
    }

  , getPendingUpdateIDs: function () {
      return _updatedOnServer;
    }

  , isLocalTaskPending: function ( id ) {
      return _.values( _localUpdatePending ).indexOf( id ) > -1;
    }

  , isGroupUpdatePending: function ( id ) {
      return _updatedOnServer.indexOf( id ) > -1;
    }

  , findGroupByKeyValue: function ( key, value ) {
      return _.find( _groups, function ( group ) {
        return group[ key ] === value;
      });
    }

  , getGroup: function ( id ) {
      return _groups[ id ];
    }

  , getAllGroups: function () {
      return _.values( _groups );
    }

});

GroupsStore.dispatchToken = FreeNASDispatcher.register( function ( payload ) {
  var action = payload.action;

  switch ( action.type ) {

    case ActionTypes.RECEIVE_GROUPS_LIST:

      var updatedGroupIDs = _.pluck( action.groupsList, PRIMARY_KEY );

      // When receiving new data, we can comfortably resolve anything that may
      // have had an outstanding update indicated by the Middleware.
      if ( _updatedOnServer.length > 0 ) {
        _updatedOnServer = _.difference( _updatedOnServer, updatedGroupIDs );
      }

      // Updated groups come from the middleware as an array, but we store the
      // data as an object keyed by the PRIMARY_KEY. Here, we map the changed
      // groups into the object.
      action.groupsList.map( function ( group ) {
        _groups[ group [ PRIMARY_KEY ] ] = group;
      });
      GroupsStore.emitChange();
      break;

    case ActionTypes.MIDDLEWARE_EVENT:
      var args = action.eventData.args;
      var updateData = args[ "args" ];

      if ( args[ "name" ] === UPDATE_MASK ) {
        if ( updateData[ "operation" ] === "delete" ) {
          _groups = _.omit( _groups, updateData["ids"] );
        } else if ( updateData[ "operation" ] === "create"
                  || updateData[ "operation" ] === "update" ) {
          Array.prototype.push.apply( _updatedOnServer, updateData["ids"] );
          GroupsMiddleware.requestGroupsList( _updatedOnServer );
        }
        GroupsStore.emitChange();

      } else if ( args[ "name" ] === "task.updated"
                && updateData["state"] === "FINISHED" ) {
        delete _localUpdatePending[ updateData["id"] ];
      }
      break;

    case ActionTypes.RECEIVE_GROUP_UPDATE_TASK:
      _localUpdatePending[ action.taskID ] = action.groupID;
      GroupsStore.emitChange();
      break;

    default:
    // Do Nothing
  }

});

module.exports = GroupsStore;
