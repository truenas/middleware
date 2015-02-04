// Networks Flux Store
// ==================

"use strict";

var _            = require("lodash");
var EventEmitter = require("events").EventEmitter;

var FreeNASDispatcher = require("../dispatcher/FreeNASDispatcher");
var FreeNASConstants  = require("../constants/FreeNASConstants");

var ActionTypes  = FreeNASConstants.ActionTypes;
var CHANGE_EVENT = "change";

var _networks = [];

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

  ,  getAllNetworks: function() {
      return _networks;
   }

});

NetworksStore.dispatchToken = FreeNASDispatcher.register( function( payload) {
  var action = payload.action;

  switch( action.type ) {

    case ActionTypes.RECEIVE_RAW_NETWORKS:
      _networks = action.rawNetworksList;
      NetworksStore.emitChange();
      break;

    default:
      //Do nothing
  }
});

module.exports = NetworksStore;
