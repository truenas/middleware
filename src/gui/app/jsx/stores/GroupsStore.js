// Groups Flux Store
// -----------------

"use strict";

import _ from "lodash";
import { EventEmitter } from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";
import FluxBase from "./FluxBase";

import GM from "../middleware/GroupsMiddleware";

var CHANGE_EVENT = "change";
var UPDATE_MASK  = "groups.changed";
var PRIMARY_KEY  = "groupID";

var _localUpdatePending = {};
var _updatedOnServer    = [];
var _groups = {};

const GROUP_SCHEMA =
  { type: "object"
  , properties:
    { groupName: { type: "string" }
    , groupID: { type: "number" }
    , builtIn: { type: [ "boolean", "null" ] }
    }
  };

const GROUP_LABELS =
  { type: "object"
  , properties:
    { groupName: "Group Name"
    , groupID: "Group ID"
    , builtIn: "Built-in System Group"
    }
  };

const KEY_TRANSLATION =
  { name: "groupName"
  , id: "groupID"
  , builtin: "builtIn"
  };

class GroupsStore extends FluxBase {

  constructor () {
    super();

    this.dispatchToken = FreeNASDispatcher.register(
      handlePayload.bind( this )
    );

    this.KEY_UNIQUE = "groupName";
    this.ITEM_SCHEMA = GROUP_SCHEMA;
    this.ITEM_LABELS = GROUP_LABELS;
  }

  get updateMask () {
    return UPDATE_MASK;
  }

  get pendingUpdateIDs () {
    return _updatedOnServer;
  }

  get groups () {
    return _.values( _groups );
  }

  getGroup ( groupID ) {
    return _groups[ groupID ];
  }

  isLocalTaskPending ( groupID ) {
    return _.values( _localUpdatePending ).indexOf( groupID ) > -1;
  }
  isGroupUpdatePending ( groupID ) {
    return _updatedOnServer.indexOf( groupID ) > -1;
  }

  findGroupByKeyValue ( key, value ) {
    return _.find( _groups
                 , function ( group ) {
                   return group[ key ] === value;
                 }
                 );
  }

  // Converts a group back into a middleware-compatible mode.
  // TODO: Put this into FluxBase if we keep the current method of key
  // translation.
  reverseKeyTranslation ( group ) {
    let reverseKeys = _.invert( KEY_TRANSLATION );

    let newGroup = FluxBase.rekeyForClient( group, reverseKeys );

    return newGroup;
  }

  // Will return the first available GID above 1000 (to be used as a default).
  // TODO: Replace this with a middleware call to determine the next available
  // gid.
  get nextGID () {

    let nextGID = 1000;

    // loop until it finds a GID that's not in use
    while ( _.has( _groups, nextGID ) ) {
      nextGID++;
    }

    return nextGID;

  }

}

function handlePayload ( payload ) {
  const ACTION = payload.action;

  switch ( ACTION.type ) {

    case ActionTypes.RECEIVE_GROUPS_LIST:

      ACTION.groupsList.forEach(
        function convertGroups ( group ) {
          _groups[ group[ "id" ] ] = FluxBase.rekeyForClient( group
                                                            , KEY_TRANSLATION
                                                            );
        }
        , this
      );

      this.emitChange();
      break;

    case ActionTypes.MIDDLEWARE_EVENT:
      let args = ACTION.eventData.args;
      let updateData = args[ "args" ];

      if ( args[ "name" ] === UPDATE_MASK ) {
        if ( updateData[ "operation" ] === "delete" ) {
          _groups = _.omit( _groups, updateData["ids"] );
        } else if ( updateData[ "operation" ] === "create"
                  || updateData[ "operation" ] === "update" ) {
          Array.prototype.push.apply( _updatedOnServer, updateData["ids"] );
          GM.requestGroupsList( _updatedOnServer );
        }
        this.emitChange();

      } else if ( args[ "name" ] === "task.updated"
                && updateData["state"] === "FINISHED" ) {
        delete _localUpdatePending[ updateData["id"] ];
      }
      break;

    case ActionTypes.RECEIVE_GROUP_UPDATE_TASK:
      _localUpdatePending[ ACTION.taskID ] = ACTION.groupID;
      this.emitChange();
      break;

    default:
    // Do Nothing
  }

};

export default new GroupsStore ();
