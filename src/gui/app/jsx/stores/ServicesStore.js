// Services Flux Store
// ----------------

"use strict";

var _            = require("lodash");
var EventEmitter = require("events").EventEmitter;

var FreeNASDispatcher = require("../dispatcher/FreeNASDispatcher");
var FreeNASConstants  = require("../constants/FreeNASConstants");

var ActionTypes  = FreeNASConstants.ActionTypes;
var CHANGE_EVENT = "change";

var _services = [];
var _scheduledForStateUpdate = {};
var ServicesStore = _.assign( {}, EventEmitter.prototype, {

    emitChange: function() {
      this.emit( CHANGE_EVENT );
    }

  , addChangeListener: function( callback ) {
      this.on( CHANGE_EVENT, callback );
    }

  , removeChangeListener: function( callback ) {
      this.removeListener( CHANGE_EVENT, callback );
    }

  , findServiceByKeyValue: function( key, value ) {
      var predicate = {};
          predicate[key] = value;

      return _.find( _services, predicate );
    }

  , getAllServices: function() {
      return _services;
    }

});

ServicesStore.dispatchToken = FreeNASDispatcher.register( function( payload ) {
  var action = payload.action;

  switch( action.type ) {

    case ActionTypes.RECEIVE_RAW_SERVICES:
      _services = action.rawServices;
      ServicesStore.emitChange();
      break;

    case ActionTypes.RECEIVE_SERVICE_UPDATE_TASK:
      console.log("service update task");
      _scheduledForStateUpdate[ action.taskID ] = action.serviceName;
      ServicesStore.emitChange();
      break;


    default:
      // No action
  }
});

module.exports = ServicesStore;
