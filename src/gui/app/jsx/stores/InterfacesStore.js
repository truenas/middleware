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
var _interfaces           = [];

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

  // Returns true if the selected interface is in the
  // list of interfaces with pending updates.
  , isLocalTaskPending: function ( interfaceName ) {
      return _.values( _localUpdatePending ).indexof( interfaceName ) > -1;
    }

  // Returns true if selected interface is in the list of updated interfaces.
  , isInterfaceUpdatePending: function ( linkAddress ) {
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

  , getAllInterfaces: function () {
    return _interfaces;
  }

});

InterfacesStore.dispatchToken = FreeNASDispatcher.register( function ( payload ) {
  let action = payload.action;

  switch ( action.type ) {

    case ActionTypes.RECEIVE_INTERFACES_LIST:

      // Re-map the complex interface objects into flat ones.
      // TODO: Account for multiple aliases and static configurations.
      let mapInterface = function ( currentInterface ) {

        let newInterface = {};

        // Make the block below less absurdly wide.
        let status  = currentInterface.status;

        // Initialize desired fields with existing ones.
        newInterface[ "name" ] = currentInterface[ "name" ]
                               ? currentInterface[ "name" ]
                               : null;
        newInterface[ "ip" ] = status[ "aliases" ][1]
                             ? status[ "aliases" ][1][ "address" ]
                             : "--";
        newInterface[ "link_state" ] = status[ "link-state" ]
                                     ? status[ "link-state" ]
                                     : null;
        newInterface[ "link_address" ] = status[ "link-address" ]
                                     ? status[ "link-address" ]
                                     : null;
        newInterface[ "flags" ] = status[ "flags" ]
                                ? status[ "flags" ]
                                : [];
        newInterface[ "netmask" ] = status[ "aliases" ][1]
                                  ? status[ "aliases" ][1][ "netmask" ]
                                  : null;
        newInterface[ "enabled" ] = currentInterface[ "enabled" ]
                                  ? true
                                  : false;
        newInterface[ "dhcp" ] = currentInterface[ "dhcp" ]
                               ? true
                               : false;
        newInterface[ "status" ] = status;
        newInterface[ "mtu" ] = currentInterface[ "mtu" ]
                              ? currentInterface[ "mtu" ]
                              : null;

        // Figure out interface type. Only knows about Ethernet right now.
        // TODO: There are tons more types that could show up. See:
        // http://fxr.watson.org/fxr/source/net/if_types.h?v=FREEBSD10
        // ETHER and FIBRECHANNEL will definitely have different logos.
        // Many of the others, such as LAPD and CARP will be discarded and only
        // used by other parts of the UI. The vast majority of that list doesn'
        // matter.
        newInterface[ "type"] = currentInterface[ "type" ] === "ETHER"
                              ? "Ethernet"
                              : "Unknown";

        // Determine Internet Protocol version
        if ( !status[ "aliases" ][1] ) {
          newInterface[ "ip_version" ] = "IP";
        } else {

          switch ( status[ "aliases" ][1][ "family" ] ) {

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
        switch ( newInterface[ "type" ] ) {

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
      let args = action.eventData.args;

      if ( args["name"] === UPDATE_MASK ) {
        let updateData = args["args"];

        if ( updateData ["operation"] === "update" ) {

          // Not reall sure this is doing something useful.
          Array.prototype.push.apply( _updatedOnServer, updateData["ids"] );
          InterfacesMiddleware.requestInterfacesList( );
        }
      }

      InterfacesStore.emitChange();
      break;

    case ActionTypes.RECEIVE_INTERFACE_CONFIGURE_TASK:
      _localUpdatePending[ action.taskID ] = action.interfaceName;
      InterfacesStore.emitChange();
      break;

    default:
    // Do nothing
  }
});

module.exports = InterfacesStore;
