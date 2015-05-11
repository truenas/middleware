// Networks Flux Store
// ==================

"use strict";

import _ from "lodash";
import EventEmitter from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

import NetworksMiddleware from "../middleware/NetworksMiddleware";

var CHANGE_EVENT = "change";
var UPDATE_MASK  = "networks.changed";

var _updatedOnServer    = [];
var _localUpdatePending = {};
var _networks           = [];

var NetworksStore = _.assign( {}, EventEmitter.prototype, {

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

// Returns true if the selected network is in the
// list of networks with pending updates.
  , isLocalTaskPending: function( linkAddress ) {
      return _.values(_localUpdatePending ).indexof( linkAddress ) > -1;
    }

// Returns true if selected network is in the list of updated networks.
  , isNetworkUpdatePending: function( linkAddress ) {
      return _updatedOnServer.indexof( linkAddress ) > -1;
    }

  , findNetworkByKeyValue: function ( key, value ) {
      return _.find( _networks, function ( network ) {
        return network[ key ] === value;
      });
  }

  , getNetwork: function ( linkAddress ) {
      return _networks[ linkAddress ];
  }

  ,  getAllNetworks: function () {
      return _networks;
   }

});

NetworksStore.dispatchToken = FreeNASDispatcher.register( function( payload) {
  var action = payload.action;

  switch( action.type ) {

    case ActionTypes.RECEIVE_RAW_NETWORKS:

      // Re-map the complex network objects into flat ones.
      // TODO: Account for multiple aliases and static configurations.
      var mapNetwork = function ( currentNetwork ) {

        var newNetwork = {};

        // Make the block below less absurdly wide.
        var status  = currentNetwork.status;

        // Initialize desired fields with existing ones.
        newNetwork[ "name" ]         = currentNetwork[ "name" ] ? currentNetwork[ "name" ] : null;
        newNetwork[ "ip" ]           = status[ "aliases" ][1] ? status[ "aliases" ][1][ "address" ] : "--";
        newNetwork[ "link_state" ]   = status[ "link-state" ] ? status[ "link-state" ] : null;
        newNetwork[ "link_address" ] = status[ "link-address" ] ? status[ "link-address" ] : null;
        newNetwork[ "flags" ]        = status[ "flags" ] ? status[ "flags" ] : [];
        newNetwork[ "netmask" ]      = status[ "aliases" ][1] ? status[ "aliases" ][1][ "netmask" ] : null;
        newNetwork[ "enabled" ]      = currentNetwork[ "enabled" ] ? true : false;
        newNetwork[ "dhcp" ]         = currentNetwork[ "dhcp" ] ? true : false;

        // Figure out interface type. Only knows about Ethernet right now.
        // TODO: There are tons more types that could show up. See:
        // http://fxr.watson.org/fxr/source/net/if_types.h?v=FREEBSD10
        // ETHER and FIBRECHANNEL will definitely have different logos.
        // Many of the others, such as LAPD and CARP will be discarded and only
        // used by other parts of the UI. The vast majority of that list doesn't matter.
        newNetwork[ "type"]          = currentNetwork[ "type" ] === "ETHER" ? "Ethernet" : "Unknown";

        // Determine Internet Protocol version
        if (!status[ "aliases" ][1]) {
          newNetwork[ "ip_version" ] = "IP";
        } else {
          switch (status[ "aliases" ][1][ "family" ]) {
            case "INET":
              newNetwork[ "ip_version" ] = "IPv4";
              break;
            case "INET6":
              newNetwork[ "ip_version" ] = "IPv6";
              break;
            default:
            // Nothing to do here.
          }
        }

        // Map the interface type and/or status to an appropriate icon.
        // TODO: This also needs to handle other interface types.
        switch (newNetwork[ "type"]) {
          // Ethernet gets the FontAwesome "exchange" icon for now.
          // TODO: Other conditions, such as different icons for connected and
          // disconnected interfaces of different types.
          case "Ethernet":
          newNetwork[ "font_icon" ] = "exchange";
          break;
          default:
          newNetwork[ "icon" ] = null;
          break;
        }

        return newNetwork;
      };

      _networks = action.rawNetworksList.map( mapNetwork );
      NetworksStore.emitChange();
      break;

    case ActionTypes.MIDDLEWARE_EVENT:
      var args = action.eventData.args;

      if ( args["name"] === UPDATE_MASK ) {
        var updateData = args["args"];

        if (updateData ["operation"] === "update" ) {
          Array.prototype.push.apply( _updatedOnServer, updateData["ids"] );
          NetworksMiddleware.requestUsersList( _updatedOnServer );
        }
      }
      break;

    case ActionTypes.RECEIVE_NETWORK_UPDATE_TASK:
      _localUpdatePending[ action.taskID ] = action.networkID;
      NetworksStore.emitChange();
      break;

    case ActionTypes.RESOLVE_USER_UPDATE_TASK:
      delete _localUpdatePending [ action.taskID ];
      NetworksStore.emitChange();
      break;

    default:
      //Do nothing
  }
});

module.exports = NetworksStore;
