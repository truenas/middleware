define(["dojo/on", "dojo/dom", "dojo/query"], function(on, dom){
	function handler(selector, type){
		// summary:
		//		Creates a handler function usable as a simulated event to dojo/on,
		//		which fires only if the mouse is moving into or out of the node of
		//		interest indicated by the selector.
		//		This is similar, but not identical, to what dojo/mouse does.
		// selector: String
		//		Query selector for event delegation.
		// type: String
		//		Event to delegate on (mouseover or mouseout).
		
		return function(node, listener){
			return on(node, selector + ":" + type, function(evt){
				if(!dom.isDescendant(evt.relatedTarget, this)){
					return listener.call(this, evt);
				}
			});
		};
	}
	
	return {
		// Provide enter/leave events for rows, cells, and header cells.
		// (Header row is trivial since there's only one.)
		enterRow: handler(".dgrid-content .dgrid-row", "mouseover"),
		enterCell: handler(".dgrid-content .dgrid-cell", "mouseover"),
		enterHeaderCell: handler(".dgrid-header .dgrid-cell", "mouseover"),
		leaveRow: handler(".dgrid-content .dgrid-row", "mouseout"),
		leaveCell: handler(".dgrid-content .dgrid-cell", "mouseout"),
		leaveHeaderCell: handler(".dgrid-header .dgrid-cell", "mouseout"),
		
		// Also expose the handler function, so people can do what they want.
		createDelegatingHandler: handler
	};
});