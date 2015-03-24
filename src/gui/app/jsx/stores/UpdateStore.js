// Update Data Flux Store
// ----------------

"use strict";

var _            = require("lodash");
var EventEmitter = require("events").EventEmitter;

var FreeNASDispatcher = require("../dispatcher/FreeNASDispatcher");
var FreeNASConstants  = require("../constants/FreeNASConstants");

var ActionTypes  = FreeNASConstants.ActionTypes;
var CHANGE_EVENT = "change";

var _updateData = {};

var UpdateStore = _.assign( {}, EventEmitter.prototype, {

    emitChange: function(changeType) {
      this.emit( CHANGE_EVENT );
    }

  , addChangeListener: function( callback ) {
      this.on( CHANGE_EVENT, callback );
    }

  , removeChangeListener: function( callback ) {
      this.removeListener( CHANGE_EVENT, callback );
    }

  , getUpdate: function(name) {
      return _updateData[name];
    }


});

UpdateStore.dispatchToken = FreeNASDispatcher.register( function( payload ) {
  var action = payload.action;

  switch( action.type ) {

    case ActionTypes.RECEIVE_UPDATE_DATA:
      _updateData[action.updateInfoName] = action.updateInfo;
      UpdateStore.emitChange();
      break;

    default:
      // No action
  }
});

module.exports = UpdateStore;
