// Networks Flux Store
// ==================

"use strict";

var _            = require("lodash");
var EventEmitter = require("events").EventEmitter;

var FreeNASDispatcher = require("../dispatcher/FreeNASDispatcher");
var FreeNASConstants  = require("../constants/FreeNASConstants");

var NetworksMiddleware = require("../middleware/NetworksMiddleware");

var ActionTypes  = FreeNASConstants.ActionTypes;
var CHANGE_EVENT = "change";
var UPDATE_MASK  = "networks.changed";

var _updatedOnServer    = [];
var _localUpdatePending = {};
var _networks           = [];

var NetworksStore = _.assign( {}, EventEmitter.prototype, {

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

  , getPendingUpdateIDs: function() {
     return _updatedOnServer;
    }

// Returns true if the selected network is in the
// list of networks with pending updates.
  , isLocalTaskPending: function( id ) {
      return _.values(_localUpdatePending ).indexof( id ) > -1;
    }

// Returns true if selected network is in the list of updated networks.
  , isNetworkUpdatePending: function( id ) {
      return _updatedOnServer.indexof( id ) > -1;
    }

  , findNetworkByKeyValue: function ( key, value ) {
      return _.find( _networks, function ( network ) {
        return network[ key ] === value;
      });
  }

  , getNetwork: function ( id ) {
      return _networks[ id ];
  }

  ,  getAllNetworks: function() {
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

        var tempNetwork = {};

        // Make the block below less absurdly wide
        var status  = currentNetwork.status;

        // Initialize desired fields with existing ones.
        tempNetwork[ "name" ]         = currentNetwork[ "name" ] ? currentNetwork[ "name" ] : null;
        tempNetwork[ "ip" ]           = status[ "aliases" ][1] ? status[ "aliases" ][1][ "address" ] : "--";
        tempNetwork[ "link_state" ]   = status[ "link-state" ] ? status[ "link-state" ] : null;
        tempNetwork[ "link_address" ] = status[ "link-address" ] ? status[ "link-address" ] : null;
        tempNetwork[ "flags" ]        = status[ "flags" ] ? status[ "flags" ] : [];
        tempNetwork[ "netmask" ]      = status[ "aliases" ][1] ? status[ "aliases" ][1][ "netmask" ] : null;
        tempNetwork[ "enabled" ]      = currentNetwork[ "enabled" ] ? currentNetwork[ "enabled" ] : false;
        tempNetwork[ "dhcp" ]         = currentNetwork[ "dhcp" ] ? currentNetwork[ "dhcp" ] : false;

        //Figure out interface type. Only knows about Ethernet right now.
        tempNetwork[ "type"]          = currentNetwork[ "type" ] == "ETHER" ? "Ethernet" : "Unknown";

        // Determine Internet Protcol version
        if (!status[ "aliases" ][1]) {
          tempNetwork[ "ip_version" ] = "IP";
        } else {
          switch (status[ "aliases" ][1][ "family" ]) {
            case "INET":
              tempNetwork[ "ip_version" ] = "IPv4";
              break;
            case "INET6":
              tempNetwork[ "ip_version" ] = "IPv6";
              break;
            default:
            // Nothing to do here.
          }
        }
        return tempNetwork;
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
