// Groups Flux Store
// -----------------

"use strict";

var _            = require("lodash");
var EventEmitter = require("events").EventEmitter;

var FreeNASDispatcher = require("../dispatcher/FreeNASDispatcher");
var FreeNASConstants  = require("../constants/FreeNASConstants");

var GroupsMiddleware = require("../middleware/GroupsMiddleware");
var UsersMiddleware = require("../middleware/UsersMiddleware");

var ActionTypes  = FreeNASConstants.ActionTypes;
var CHANGE_EVENT = "change";
var UPDATE_MASK  = "groups.changed";
var PRIMARY_KEY  = "groupid";

var _localUpdatePending = {};
var _updatedOnServer    = [];
var _groups = [];

var GroupsStore = _.assign( {}, EventEmitter.prototype, {

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

  , getGroup: function( groupid ) {
      return _groups[ groupid ];
    }

  , getAllGroups: function() {
      return _.values( _groups );
    }

});

GroupsStore.dispatchToken = FreeNASDispatcher.register( function( payload ) {
  var action = payload.action;

  switch( action.type ) {

    case ActionTypes.RECEIVE_GROUPS_LIST:

      action.groupsList.map( function ( group ) {
        _groups[ group [ PRIMARY_KEY ] ] = group;
      });
      
      GroupsStore.emitChange();
      break;

    case ActionTypes.MIDDLEWARE_EVENT:
      var args = action.eventData.args;

      if ( args["name"] === UPDATE_MASK ) {
        var updateData = args["args"];

        if ( updateData ["operation"] === "update" ) {
          Array.prototype.push.apply( _updatedOnServer, updateData["ids"] );
          GroupsMiddleware.requestGroupsList( _updatedOnServer );
        }
      }
      break;

    case ActionTypes.RECEIVE_GROUP_UPDATE_TASK:
      _localUpdatePending[ action.taskID ] = action.groupID;
      GroupsStore.emitChange();
      break;

    case ActionTypes.RESOLVE_GROUP_UPDATE_TASK:
      delete _localUpdatePending [ action.taskID ];
      GroupsStore.emitChange();
      break;

    default:
      // Do Nothing
  }

});

module.exports = GroupsStore;
