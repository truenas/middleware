// Interfaces Flux Store
// =====================

"use strict";

import _ from "lodash";
import EventEmitter from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

import InterfacesMiddleware from "../middleware/InterfacesMiddleware";

const CHANGE_EVENT = "change";
const UPDATE_MASK  = "network.interface.changed";

var _updatedOnServer    = [];
var _localUpdatePending = {};
var _interfaces         = {};

const INTERFACE_SCHEMA =
  { type: "object"
  , properties:
    { status:
        { type: "object"
        , properties:
          { "link-state"    : { type: "string" }
          , "link-address"  : { type: "string" }
          , flags:
            { enum:
              [ "DRV_RUNNING"
              , "UP"
              , "BROADCAST"
              , "SIMPLEX"
              , "MULTICAST"
              ]
            , type: "string"
            }
          , name            : { type: "string" }
          , aliases:
            { items : { $ref: "network-interface-alias" }
            , type  : "array"
            }
          }
        }
    , name    : { type: "string" }
    , dhcp    : { type: "boolean" }
    , enabled : { type: "boolean" }
    , aliases:
      { items : { $ref: "network-interface-alias" }
      , type  : "array"
      }
    , type    : { type: "string" }
    , id      : { type: "string" }
    , mtu     : { type: [ "integer", "null" ] }
    }
  };

const INTERFACE_LABELS =
    { status              : "Status"
    , "link-state"        : "Link State"
    , "link-address"      : "Link Address"
    , flags               : "Flags"
    , name                : "Interface Name"
    , aliases             : "Aliases"
    , dhcp                : "DHCP"
    , enabled             : "Enabled"
    , type                : "Type"
    , id                  : "Interface ID"
    , mtu                 : "MTU"
  };

var InterfacesStore = _.assign( {}, EventEmitter.prototype, {

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

  , getPendingUpdateNames: function () {
    return _updatedOnServer;
  }

  /**
   * Check if the selected interface is in the list of interfaces with pending updates.
   * @param  {String} name The interface name.
   * @return {Boolean}
   */
  , isLocalTaskPending: function ( name ) {
      return _.values( _localUpdatePending ).indexof( name ) > -1;
    }

  /**
   * Check if the selected interface is in the list of updated interfaces.
   * @param  {String} name The interface name.
   * @return {Boolean}
   */
  , isInterfaceUpdatePending: function ( name ) {
      return _updatedOnServer.indexof( name ) > -1;
    }

  , findInterfaceByKeyValue: function ( key, value ) {
    var predicate = {};
    predicate[key] = value;
    return _.find( _interfaces, predicate );
  }

  , getInterfaceSchema: function () {
      return INTERFACE_SCHEMA;
    }

  , getInterfaceLabels: function () {
      return INTERFACE_LABELS;
    }

  , getInterface: function ( name ) {
    return _interfaces[ name ];
  }

  , getAllInterfaces: function () {
    return _.values( _interfaces );
  }

});

InterfacesStore.dispatchToken = FreeNASDispatcher.register( function ( payload ) {
  var action = payload.action;

  switch ( action.type ) {

    case ActionTypes.RECEIVE_INTERFACES_LIST:
      var updatedInterfaceNames = _.pluck( action.rawInterfacesList, 'name' );

      if ( _updatedOnServer.length ) {
        _updatedOnServer = _.difference( _updatedOnServer, updatedInterfaceNames );
      }

      action.rawInterfacesList.map( function ( _interface ) {
        _interfaces[ _interface.name ] = _interface;
      })

      InterfacesStore.emitChange();
      break;

    case ActionTypes.MIDDLEWARE_EVENT:
      var args = action.eventData.args;
      var updateData = args['args'];

      if ( args["name"] === UPDATE_MASK ) {
        /*let updateData = args["args"];

        if ( updateData ["operation"] === "update" ) {

          // Not reall sure this is doing something useful.
          Array.prototype.push.apply( _updatedOnServer, updateData["ids"] );
          InterfacesMiddleware.requestInterfacesList( );
        }*/
      }

      //InterfacesStore.emitChange();
      break;

    case ActionTypes.RECEIVE_UP_INTERFACE_TASK:
    case ActionTypes.RECEIVE_DOWN_INTERFACE_TASK:
    case ActionTypes.RECEIVE_INTERFACE_CONFIGURE_TASK:
      _localUpdatePending[ action.taskID ] = action.interfaceName;
      InterfacesStore.emitChange();
      break;

    default:
    // Do nothing
  }
});

module.exports = InterfacesStore;
