// Sharing Action Creators
// ==================================
// Receive and handle events from the middleware, and call the dispatcher.

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class SharesActionCreators {

	recieveSharesList ( sharesList ) {
		FreeNASDispatcher.handleMiddlewareAction(
			{
				type: ActionTypes.RECIEVE_SHARES_LIST
				, sharesList: sharesList
			}
		);
	}

	recieveShareUpdateTask ( taskID, shareID ) {
		FreeNASDispatcher.handleMiddlewareAction(
			{ type: ActionTypes.RECIEVE_SHARE_UPDATE_TASK
				, taskID: taskID
				, shareID: shareID
			}
		);
	}

};
	
export default new SharesActionCreators();