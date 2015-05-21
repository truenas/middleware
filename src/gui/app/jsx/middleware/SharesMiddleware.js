"use strict";

import MiddlewareClient from "../middleware/MiddlewareClient";

import SharesActionCreators from "../actions/SharesActionCreators";

module.exports = {

	subscribe: function (componentID) {
		MiddlewareClient.subscribe( [ "shares.changed" ] , componentID );
		MiddlewareClient.subscribe( [ "task.*" ], componentID );
	}

	, unsubscribe: function (componentID ) {
		MiddlewareClient.unsubscribe( [ "shares.changed" ] , componentID );
		MiddlewareClient.unsubscribe( [ "task.*" ], componentID );
	}

	, requestSharesList: function  () {
		MiddlewareClient.request( "shares.query", [], function (sharesList) {
			SharesActionCreators.receiveSharesList( sharesList );
		});
	}

	, createShare: function ( newShareProps ) {
		MiddlewareClient.request( "task.submit"
															, [ "shares.create" , [ newShareProps ] ] 
															, this.createShareCallback
															);
	}

	, createShareCallback: function ( taskID, shareID ) {
		SharesActionCreators.recieveShareUpdateTask( taskID, shareID );
	}

	, updateShare: function ( shareID, props ) {
		MiddlewareClient.request( "task.submit" 
														,	[ "shares.update", [shareID, props ]]
														, this.updateShareCallback
														);
	}

	, updateShareCallback: function ( taskID, shareID ) {
		SharesActionCreators.recieveShareUpdateTask( taskID, shareID );
	}

	, deleteShare: function ( shareID ) {
		MiddlewareClient.request( "task.submit" 
														,	[ "shares.delete", [ shareID ] ]
														, this.deleteShareCallback
														);
	}

	, deleteShareCallback ( taskID, shareID ) {
		SharesActionCreators.recieveShareUpdateTask( taskID, shareID );
	}
}