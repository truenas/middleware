// Interfaces Flux Store
// ==================

"use strict";

import _ from "lodash";
import EventEmitter from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

import InterfacesMiddleware from "../middleware/InterfacesMiddleware";

var CHANGE_EVENT = "change";
var UPDATE_MASK  = "networks.changed";

var _updatedOnServer    = [];
var _localUpdatePending = {};
var _interfaces           = [];

var InterfacesStore = _.assign( {}, EventEmitter.prototype, {

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

// Returns true if the selected interface is in the
// list of interfaces with pending updates.
  , isLocalTaskPending: function( linkAddress ) {
      return _.values(_localUpdatePending ).indexof( linkAddress ) > -1;
    }

// Returns true if selected interface is in the list of updated interfaces.
  , isInterfaceUpdatePending: function( linkAddress ) {
      return _updatedOnServer.indexof( linkAddress ) > -1;
    }

  , findInterfaceByKeyValue: function ( key, value ) {
      // 'interface' is a reserved word. arg renamed 'thisInterface'.
      return _.find( _interfaces, function ( thisInterface ) {
        return thisInterface[ key ] === value;
      });
  }

  , getInterface: function ( linkAddress ) {
      return _interfaces[ linkAddress ];
  }

  ,  getAllInterfaces: function () {
      return _interfaces;
   }

});

InterfacesStore.dispatchToken = FreeNASDispatcher.register( function( payload) {
  var action = payload.action;

  switch( action.type ) {

    case ActionTypes.RECEIVE_RAW_NETWORKS:

      // Re-map the complex interface objects into flat ones.
      // TODO: Account for multiple aliases and static configurations.
      var mapInterface = function ( currentInterface ) {

        var newInterface = {};

        // Make the block below less absurdly wide.
        var status  = currentInterface.status;

        // Initialize desired fields with existing ones.
        newInterface[ "name" ]         = currentInterface[ "name" ] ? currentInterface[ "name" ] : null;
        newInterface[ "ip" ]           = status[ "aliases" ][1] ? status[ "aliases" ][1][ "address" ] : "--";
        newInterface[ "link_state" ]   = status[ "link-state" ] ? status[ "link-state" ] : null;
        newInterface[ "link_address" ] = status[ "link-address" ] ? status[ "link-address" ] : null;
        newInterface[ "flags" ]        = status[ "flags" ] ? status[ "flags" ] : [];
        newInterface[ "netmask" ]      = status[ "aliases" ][1] ? status[ "aliases" ][1][ "netmask" ] : null;
        newInterface[ "enabled" ]      = currentInterface[ "enabled" ] ? true : false;
        newInterface[ "dhcp" ]         = currentInterface[ "dhcp" ] ? true : false;

        // Figure out interface type. Only knows about Ethernet right now.
        // TODO: There are tons more types that could show up. See:
        // http://fxr.watson.org/fxr/source/net/if_types.h?v=FREEBSD10
        // ETHER and FIBRECHANNEL will definitely have different logos.
        // Many of the others, such as LAPD and CARP will be discarded and only
        // used by other parts of the UI. The vast majority of that list doesn't matter.
        newInterface[ "type"]          = currentInterface[ "type" ] === "ETHER" ? "Ethernet" : "Unknown";

        // Determine Internet Protocol version
        if (!status[ "aliases" ][1]) {
          newInterface[ "ip_version" ] = "IP";
        } else {
          switch (status[ "aliases" ][1][ "family" ]) {
            case "INET":
              newInterface[ "ip_version" ] = "IPv4";
              break;
            case "INET6":
              newInterface[ "ip_version" ] = "IPv6";
              break;
            default:
            // Nothing to do here.
          }
        }

        // Map the interface type and/or status to an appropriate icon.
        // TODO: This also needs to handle other interface types.
        switch (newInterface[ "type"]) {
          // Ethernet gets the FontAwesome "exchange" icon for now.
          // TODO: Other conditions, such as different icons for connected and
          // disconnected interfaces of different types.
          case "Ethernet":
          newInterface[ "font_icon" ] = "exchange";
          break;
          default:
          newInterface[ "icon" ] = null;
          break;
        }

        return newInterface;
      };

      _interfaces = action.rawInterfacesList.map( mapInterface );
      InterfacesStore.emitChange();
      break;

    case ActionTypes.MIDDLEWARE_EVENT:
      var args = action.eventData.args;

      if ( args["name"] === UPDATE_MASK ) {
        var updateData = args["args"];

        if (updateData ["operation"] === "update" ) {
          Array.prototype.push.apply( _updatedOnServer, updateData["ids"] );
          InterfacesMiddleware.requestUsersList( _updatedOnServer );
        }
      }
      break;

    case ActionTypes.RECEIVE_NETWORK_UPDATE_TASK:
      _localUpdatePending[ action.taskID ] = action.networkID;
      InterfacesStore.emitChange();
      break;

    case ActionTypes.RESOLVE_USER_UPDATE_TASK:
      delete _localUpdatePending [ action.taskID ];
      InterfacesStore.emitChange();
      break;

    default:
      //Do nothing
  }
});

module.exports = InterfacesStore;
