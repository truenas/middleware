// Widget Data Flux Store
// ----------------

"use strict";

import _ from "lodash";
import { EventEmitter } from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

var CHANGE_EVENT = "change";

var _widgetData = {};
var _dataUpdate = [];


var StatdStore = _.assign( {}, EventEmitter.prototype, {

    emitChange: function ( changeType ) {
      this.emit( CHANGE_EVENT );
    }

  , addChangeListener: function ( callback ) {
      this.on( CHANGE_EVENT, callback );
    }

  , removeChangeListener: function ( callback ) {
      this.removeListener( CHANGE_EVENT, callback );
    }

  , getWidgetData: function ( name ) {
      return _widgetData[name];
    }

  , getWidgetDataUpdate: function () {
      return _dataUpdate;
    }

});

StatdStore.dispatchToken = FreeNASDispatcher.register( function ( payload ) {
  var action = payload.action;

  switch ( action.type ) {

    case ActionTypes.RECEIVE_RAW_WIDGET_DATA:
      if ( action.rawWidgetData.data !== undefined ) {
        _widgetData[action.dataSourceName] = action.rawWidgetData.data;
      } else {
        _widgetData[action.dataSourceName] = {error: true, msg: action.rawWidgetData.message};
      }
      StatdStore.emitChange();
      break;

    case ActionTypes.MIDDLEWARE_EVENT:
      if ( action.eventData.args && _.startsWith( action.eventData.args["name"], "statd." ) ) {
        _dataUpdate = action.eventData.args;
        StatdStore.emitChange();
      }
      break;

    default:
      // No action
  }
});

module.exports = StatdStore;
