// Shares Flux Store
// -----------------

"use strict";

import _ from "lodash";
import { EventEmitter } from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

import SharesMiddleware from "../middleware/SharesMiddleware";

var CHANGE_EVENT = "change";
var UPDATE_MASK  = "shares.changed";
var PRIMARY_KEY  = "id";

var _localUpdatePending = {};
var _updatedOnServer    = [];
var _shares = {};

var SharesStore = _.assign( {}, EventEmitter.prototype, {

	emitChange: function() {
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

	, getPendingUpdateIDs: function () {
			return _updatedOnServer;
		}

	, isLocalTaskPending: function ( id ) {
			return _.values( _localUpdatePending ).indexOf( id ) > -1;
		}

	, isShareUpdatePending: function ( id ) {
			return _updatedOnServer.indexOf( id ) > -1;
		}

	, findShareByKeyValue: function ( key, value ) {
			return _.find( _shares, function ( share ) {
				return group[ key ] === value;
			});
		}

	, getShare: function ( id ) {
			return _shares[ id ];
		}

	, getAllShares: function () {
			return _.values( _shares );
		}

});

SharesStore.dispatchToken = FreeNASDispatcher.register( function ( payload ) {
	var action = payload.action;

	switch ( action.type ) {
				
		case ActionTypes.RECIEVE_SHARES_LIST:

			var updatedShareIDs = _.pluck( action.sharesList, PRIMARY_KEY );

   		// When receiving new data, we can comfortably resolve anything that may
   		// have had an outstanding update indicated by the Middleware.
   		if ( _updatedOnServer.length > 0 ) {
     		_updatedOnServer = _.difference( _updatedOnServer, updatedShareIDs );
   		}

   		// Updated groups come from the middleware as an array, but we store the
   		// data as an object keyed by the PRIMARY_KEY. Here, we map the changed
   		// groups into the object.
   		action.sharesList.map( function ( share ) {
     		_shares[ share [ PRIMARY_KEY ] ] = share;
   		});
   		SharesStore.emitChange();
   		break;

   	case ActionTypes.MIDDLEWARE_EVENT:
   		var args = action.eventData.args;
   		var updateDate = args[ "args" ];

   		if ( args[ "name" ] === UPDATE_MASK ) {
 				if ( updateData[ "operation" ] === "delete" ) {
 					_shares = _.omit( _shares, updaetData[ "ids" ] );
 				} else if ( updateData[ "operation" ] === "create"
 									|| updateData[ "operation" ] === "update" ) {
 					Array.prototype.push.apply( _updatedOnServer, updateData[ "ids" ] );
 					GroupsMiddleware.requestGroupsList( _updatedOnServer );	
 				}
 				GroupsStore.emitChange();

     	} else if ( args [ "name" ] === "task.updated"
     						&& updateData[ "state" ] === "FINISHED" ) {
     		delete _localUpdatePending[ updateData["id"] ];
     	}
     	break;
    
    case ActionTypes.RECIEVE_SHARE_UPDATE_TASK:
    	_localUpdatePending[ action.taskID ] = action.shareID;
    	SharesStore.emitChange();
    	break;

    default:
     	//Do nothing
  }
			
});

module.exports = SharesStore;