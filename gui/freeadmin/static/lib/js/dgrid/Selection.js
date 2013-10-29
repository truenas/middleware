define(["dojo/_base/kernel", "dojo/_base/declare", "dojo/_base/Deferred", "dojo/on", "dojo/has", "dojo/aspect", "./List", "dojo/has!touch?./util/touch", "put-selector/put", "dojo/query", "dojo/_base/sniff"],
function(kernel, declare, Deferred, on, has, aspect, List, touchUtil, put){

has.add("mspointer", function(global, doc, element){
	return "onmspointerdown" in element;
});

// Add feature test for user-select CSS property for optionally disabling
// text selection.
// (Can't use dom.setSelectable prior to 1.8.2 because of bad sniffs, see #15990)
has.add("css-user-select", function(global, doc, element){
	var style = element.style,
		prefixes = ["Khtml", "O", "ms", "Moz", "Webkit"],
		i = prefixes.length,
		name = "userSelect";

	// Iterate prefixes from most to least likely
	do{
		if(typeof style[name] !== "undefined"){
			// Supported; return property name
			return name;
		}
	}while(i-- && (name = prefixes[i] + "UserSelect"));

	// Not supported if we didn't return before now
	return false;
});

// Also add a feature test for the onselectstart event, which offers a more
// graceful fallback solution than node.unselectable.
has.add("dom-selectstart", typeof document.onselectstart !== "undefined");

var ctrlEquiv = has("mac") ? "metaKey" : "ctrlKey",
	hasUserSelect = has("css-user-select"),
	downType = has("mspointer") ? "MSPointerDown" : "mousedown",
	upType = has("mspointer") ? "MSPointerUp" : "mouseup";

function makeUnselectable(node, unselectable){
	// Utility function used in fallback path for recursively setting unselectable
	var value = node.unselectable = unselectable ? "on" : "",
		elements = node.getElementsByTagName("*"),
		i = elements.length;
	
	while(--i){
		if(elements[i].tagName === "INPUT" || elements[i].tagName === "TEXTAREA"){
			continue; // Don't prevent text selection in text input fields.
		}
		elements[i].unselectable = value;
	}
}

function setSelectable(grid, selectable){
	// Alternative version of dojo/dom.setSelectable based on feature detection.
	
	// For FF < 21, use -moz-none, which will respect -moz-user-select: text on
	// child elements (e.g. form inputs).  In FF 21, none behaves the same.
	// See https://developer.mozilla.org/en-US/docs/CSS/user-select
	var node = grid.bodyNode,
		value = selectable ? "text" : has("ff") < 21 ? "-moz-none" : "none";
	
	if(hasUserSelect){
		node.style[hasUserSelect] = value;
	}else if(has("dom-selectstart")){
		// For browsers that don't support user-select but support selectstart (IE<10),
		// we can hook up an event handler as necessary.  Since selectstart bubbles,
		// it will handle any child elements as well.
		// Note, however, that both this and the unselectable fallback below are
		// incapable of preventing text selection from outside the targeted node.
		if(!selectable && !grid._selectstartHandle){
			grid._selectstartHandle = on(node, "selectstart", function(evt){
				var tag = evt.target && evt.target.tagName;
				
				// Prevent selection except where a text input field is involved.
				if(tag !== "INPUT" && tag !== "TEXTAREA"){
					evt.preventDefault();
				}
			});
		}else if(selectable && grid._selectstartHandle){
			grid._selectstartHandle.remove();
			delete grid._selectstartHandle;
		}
	}else{
		// For browsers that don't support either user-select or selectstart (Opera),
		// we need to resort to setting the unselectable attribute on all nodes
		// involved.  Since this doesn't automatically apply to child nodes, we also
		// need to re-apply it whenever rows are rendered.
		makeUnselectable(node, !selectable);
		if(!selectable && !grid._unselectableHandle){
			grid._unselectableHandle = aspect.after(grid, "renderRow", function(row){
				makeUnselectable(row, true);
				return row;
			});
		}else if(selectable && grid._unselectableHandle){
			grid._unselectableHandle.remove();
			delete grid._unselectableHandle;
		}
	}
}

return declare(null, {
	// summary:
	//		Add selection capabilities to a grid. The grid will have a selection property and
	//		fire "dgrid-select" and "dgrid-deselect" events.
	
	// selectionDelegate: String
	//		Selector to delegate to as target of selection events.
	selectionDelegate: ".dgrid-row",
	
	// selectionEvents: String
	//		Event (or events, comma-delimited) to listen on to trigger select logic.
	//		Note: this is ignored in the case of touch devices.
	selectionEvents: downType + "," + upType + ",dgrid-cellfocusin",
	
	// deselectOnRefresh: Boolean
	//		If true, the selection object will be cleared when refresh is called.
	deselectOnRefresh: true,
	
	// allowSelectAll: Boolean
	//		If true, allow ctrl/cmd+A to select all rows.
	//		Also consulted by the selector plugin for showing select-all checkbox.
	allowSelectAll: false,
	
	// selection:
	//		An object where the property names correspond to 
	//		object ids and values are true or false depending on whether an item is selected
	selection: {},
	
	// selectionMode: String
	//		The selection mode to use, can be "none", "multiple", "single", or "extended".
	selectionMode: "extended",
	
	// allowTextSelection: Boolean
	//		Whether to still allow text within cells to be selected.  The default
	//		behavior is to allow text selection only when selectionMode is none;
	//		setting this property to either true or false will explicitly set the
	//		behavior regardless of selectionMode.
	allowTextSelection: undefined,
	
	// _selectionTargetType: String
	//		Indicates the property added to emitted events for selected targets;
	//		overridden in CellSelection
	_selectionTargetType: "rows",
	
	create: function(){
		this.selection = {};
		return this.inherited(arguments);
	},
	postCreate: function(){
		this.inherited(arguments);
		
		this._initSelectionEvents();
		
		// Force selectionMode setter to run
		var selectionMode = this.selectionMode;
		this.selectionMode = "";
		this._setSelectionMode(selectionMode);
	},
	
	destroy: function(){
		this.inherited(arguments);
		
		// Remove any extra handles added by Selection.
		if(this._selectstartHandle){ this._selectstartHandle.remove(); }
		if(this._unselectableHandle){ this._unselectableHandle.remove(); }
		if(this._removeDeselectSignals){ this._removeDeselectSignals(); }
	},
	
	_setSelectionMode: function(mode){
		// summary:
		//		Updates selectionMode, resetting necessary variables.
		if(mode == this.selectionMode){ return; } // prevent unnecessary spinning
		
		// Start selection fresh when switching mode.
		this.clearSelection();
		
		this.selectionMode = mode;
		
		// Compute name of selection handler for this mode once
		// (in the form of _fooSelectionHandler)
		this._selectionHandlerName = "_" + mode + "SelectionHandler";
		
		// Also re-run allowTextSelection setter in case it is in automatic mode.
		this._setAllowTextSelection(this.allowTextSelection);
	},
	setSelectionMode: function(mode){
		kernel.deprecated("setSelectionMode(...)", 'use set("selectionMode", ...) instead', "dgrid 0.4");
		this.set("selectionMode", mode);
	},
	
	_setAllowTextSelection: function(allow){
		if(typeof allow !== "undefined"){
			setSelectable(this, allow);
		}else{
			setSelectable(this, this.selectionMode === "none");
		}
		this.allowTextSelection = allow;
	},
	
	_handleSelect: function(event, target){
		// Don't run if selection mode doesn't have a handler (incl. "none"),
		// or if coming from a dgrid-cellfocusin from a mousedown
		if(!this[this._selectionHandlerName] ||
				(event.type === "dgrid-cellfocusin" && event.parentType === "mousedown") ||
				(event.type === upType && target != this._waitForMouseUp)){
			return;
		}
		this._waitForMouseUp = null;
		this._selectionTriggerEvent = event;
		
		// Don't call select handler for ctrl+navigation
		if(!event.keyCode || !event.ctrlKey || event.keyCode == 32){
			// If clicking a selected item, wait for mouseup so that drag n' drop
			// is possible without losing our selection
			if(!event.shiftKey && event.type === downType && this.isSelected(target)){
				this._waitForMouseUp = target;
			}else{
				this[this._selectionHandlerName](event, target);
			}
		}
		this._selectionTriggerEvent = null;
	},
	
	_singleSelectionHandler: function(event, target){
		// summary:
		//		Selection handler for "single" mode, where only one target may be
		//		selected at a time.
		
		var ctrlKey = event.keyCode ? event.ctrlKey : event[ctrlEquiv];
		if(this._lastSelected === target){
			// Allow ctrl to toggle selection, even within single select mode.
			this.select(target, null, !ctrlKey || !this.isSelected(target));
		}else{
			this.clearSelection();
			this.select(target);
			this._lastSelected = target;
		}
	},
	
	_multipleSelectionHandler: function(event, target){
		// summary:
		//		Selection handler for "multiple" mode, where shift can be held to
		//		select ranges, ctrl/cmd can be held to toggle, and clicks/keystrokes
		//		without modifier keys will add to the current selection.
		
		var lastRow = this._lastSelected,
			ctrlKey = event.keyCode ? event.ctrlKey : event[ctrlEquiv],
			value;
		
		if(!event.shiftKey){
			// Toggle if ctrl is held; otherwise select
			value = ctrlKey ? null : true;
			lastRow = null;
		}
		this.select(target, lastRow, value);

		if(!lastRow){
			// Update reference for potential subsequent shift+select
			// (current row was already selected above)
			this._lastSelected = target;
		}
	},
	
	_extendedSelectionHandler: function(event, target){
		// summary:
		//		Selection handler for "extended" mode, which is like multiple mode
		//		except that clicks/keystrokes without modifier keys will clear
		//		the previous selection.
		
		// Clear selection first for right-clicks outside selection and non-ctrl-clicks;
		// otherwise, extended mode logic is identical to multiple mode
		if(event.button === 2 ? !this.isSelected(target) :
				!(event.keyCode ? event.ctrlKey : event[ctrlEquiv])){
			this.clearSelection(null, true);
		}
		this._multipleSelectionHandler(event, target);
	},
	
	_toggleSelectionHandler: function(event, target){
		// summary:
		//		Selection handler for "toggle" mode which simply toggles the selection
		//		of the given target.  Primarily useful for touch input.
		
		this.select(target, null, null);
	},

	_initSelectionEvents: function(){
		// summary:
		//		Performs first-time hookup of event handlers containing logic
		//		required for selection to operate.
		
		var grid = this,
			selector = this.selectionDelegate;
		
		this._selectionEventQueues = {
			deselect: [],
			select: []
		};
		
		if(has("touch") && !has("mspointer")){
			// listen for touch taps if available
			on(this.contentNode, touchUtil.selector(selector, touchUtil.tap), function(evt){
				grid._handleSelect(evt, this);
			});
		}else{
			// listen for actions that should cause selections
			on(this.contentNode, on.selector(selector, this.selectionEvents), function(event){
				grid._handleSelect(event, this);
			});
		}
		
		// Also hook up spacebar (for ctrl+space)
		if(this.addKeyHandler){
			this.addKeyHandler(32, function(event){
				grid._handleSelect(event, event.target);
			});
		}
		
		// If allowSelectAll is true, bind ctrl/cmd+A to (de)select all rows,
		// unless the event was received from an editor component.
		// (Handler further checks against _allowSelectAll, which may be updated
		// if selectionMode is changed post-init.)
		if(this.allowSelectAll){
			this.on("keydown", function(event) {
				if(event[ctrlEquiv] && event.keyCode == 65 &&
						!/\bdgrid-input\b/.test(event.target.className)){
					event.preventDefault();
					grid[grid.allSelected ? "clearSelection" : "selectAll"]();
				}
			});
		}
		
		// Update aspects if there is a store change
		if(this._setStore){
			aspect.after(this, "_setStore", function(){
				grid._updateDeselectionAspect();
			});
		}
		this._updateDeselectionAspect();
	},
	
	_updateDeselectionAspect: function(){
		// summary:
		//		Hooks up logic to handle deselection of removed items.
		//		Aspects to an observable store's notify method if applicable,
		//		or to the list/grid's removeRow method otherwise.
		
		var self = this,
			store = this.store,
			beforeSignal,
			afterSignal;

		function ifSelected(object, idToUpdate, methodName){
			// Calls a method if the row corresponding to the object is selected.
			var id = idToUpdate || (object && object[self.idProperty || "id"]);
			if(id != null){
				var row = self.row(id),
					selection = row && self.selection[row.id];
				// Is the row currently in the selection list.
				if(selection){
					self[methodName](row, null, selection);
				}
			}
		}
		
		// Remove anything previously configured
		if(this._removeDeselectSignals){
			this._removeDeselectSignals();
		}

		// Is there currently an observable store?
		if(store && store.notify){
			beforeSignal = aspect.before(store, "notify", function(object, idToUpdate){
				if(!object){
					// Call deselect on the row if the object is being removed.  This allows the
					// deselect event to reference the row element while it still exists in the DOM.
					ifSelected(object, idToUpdate, "deselect");
				}
			});
			afterSignal = aspect.after(store, "notify", function(object, idToUpdate){
				// When List updates an item, the row element is removed and a new one inserted.
				// If at this point the object is still in grid.selection, then call select on the row so the
				// element's CSS is updated.  If the object was removed then the aspect-before has already deselected it.
				ifSelected(object, idToUpdate, "select");
			}, true);
			
			this._removeDeselectSignals = function(){
				beforeSignal.remove();
				afterSignal.remove();
			};
		}else{
			beforeSignal = aspect.before(this, "removeRow", function(rowElement, justCleanup){
				var row;
				if(!justCleanup){
					row = this.row(rowElement);
					// if it is a real row removal for a selected item, deselect it
					if(row && (row.id in this.selection)){
						this.deselect(row);
					}
				}
			});
			this._removeDeselectSignals = function(){
				beforeSignal.remove();
			};
		}
	},
	
	allowSelect: function(row){
		// summary:
		//		A method that can be overriden to determine whether or not a row (or 
		//		cell) can be selected. By default, all rows (or cells) are selectable.
		return true;
	},
	
	_fireSelectionEvent: function(type){
		// summary:
		//		Fires an event for the accumulated rows once a selection
		//		operation is finished (whether singular or for a range)
		
		var queue = this._selectionEventQueues[type],
			triggerEvent = this._selectionTriggerEvent,
			eventObject;
		
		eventObject = {
			bubbles: true,
			grid: this
		};
		if(triggerEvent){
			eventObject.parentType = triggerEvent.type;
		}
		eventObject[this._selectionTargetType] = queue;
		
		on.emit(this.contentNode, "dgrid-" + type, eventObject);
		
		// Clear the queue so that the next round of (de)selections starts anew
		this._selectionEventQueues[type] = [];
	},
	
	_fireSelectionEvents: function(){
		var queues = this._selectionEventQueues,
			type;
		
		for(type in queues){
			if(queues[type].length){
				this._fireSelectionEvent(type);
			}
		}
	},
	
	_select: function(row, toRow, value){
		// summary:
		//		Contains logic for determining whether to select targets, but
		//		does not emit events.  Called from select, deselect, selectAll,
		//		and clearSelection.
		
		var selection,
			previousValue,
			element,
			toElement,
			traverser;
		
		if(typeof value === "undefined"){
			// default to true
			value = true;
		} 
		if(!row.element){
			row = this.row(row);
		}
		
		// Check whether we're allowed to select the given row before proceeding.
		// If a deselect operation is being performed, this check is skipped,
		// to avoid errors when changing column definitions, and since disabled
		// rows shouldn't ever be selected anyway.
		if(value === false || this.allowSelect(row)){
			selection = this.selection;
			previousValue = selection[row.id];
			if(value === null){
				// indicates a toggle
				value = !previousValue;
			}
			element = row.element;
			if(!value && !this.allSelected){
				delete this.selection[row.id];
			}else{
				selection[row.id] = value;
			}
			if(element){
				// add or remove classes as appropriate
				if(value){
					put(element, ".dgrid-selected.ui-state-active");
				}else{
					put(element, "!dgrid-selected!ui-state-active");
				}
			}
			if(value !== previousValue && element){
				// add to the queue of row events
				this._selectionEventQueues[(value ? "" : "de") + "select"].push(row);
			}
			
			if(toRow){
				if(!toRow.element){
					toRow = this.row(toRow);
				}
				toElement = toRow.element;
				// find if it is earlier or later in the DOM
				traverser = (toElement && (toElement.compareDocumentPosition ? 
					toElement.compareDocumentPosition(element) == 2 :
					toElement.sourceIndex > element.sourceIndex)) ? "down" : "up";
				while(row.element != toElement && (row = this[traverser](row))){
					this._select(row, null, value);
				}
			}
		}
	},
	
	select: function(row, toRow, value){
		// summary:
		//		Selects or deselects the given row or range of rows.
		// row: Mixed
		//		Row object (or something that can resolve to one) to (de)select
		// toRow: Mixed
		//		If specified, the inclusive range between row and toRow will
		//		be (de)selected
		// value: Boolean|Null
		//		Whether to select (true/default), deselect (false), or toggle
		//		(null) the row
		
		this._select(row, toRow, value);
		this._fireSelectionEvents();
	},
	deselect: function(row, toRow){
		// summary:
		//		Deselects the given row or range of rows.
		// row: Mixed
		//		Row object (or something that can resolve to one) to deselect
		// toRow: Mixed
		//		If specified, the inclusive range between row and toRow will
		//		be deselected
		
		this.select(row, toRow, false);
	},
	
	clearSelection: function(exceptId, dontResetLastSelected){
		// summary:
		//		Deselects any currently-selected items.
		// exceptId: Mixed?
		//		If specified, the given id will not be deselected.
		
		this.allSelected = false;
		for(var id in this.selection){
			if(exceptId !== id){
				this._select(id, null, false);
			}
		}
		if(!dontResetLastSelected){
			this._lastSelected = null;
		}
		this._fireSelectionEvents();
	},
	selectAll: function(){
		this.allSelected = true;
		this.selection = {}; // we do this to clear out pages from previous sorts
		for(var i in this._rowIdToObject){
			var row = this.row(this._rowIdToObject[i]);
			this._select(row.id, null, true);
		}
		this._fireSelectionEvents();
	},
	
	isSelected: function(object){
		// summary:
		//		Returns true if the indicated row is selected.
		
		if(typeof object === "undefined" || object === null){
			return false;
		}
		if(!object.element){
			object = this.row(object);
		}
		
		// First check whether the given row is indicated in the selection hash;
		// failing that, check if allSelected is true (testing against the
		// allowSelect method if possible)
		return (object.id in this.selection) ? !!this.selection[object.id] :
			this.allSelected && (!object.data || this.allowSelect(object));
	},
	
	refresh: function(){
		if(this.deselectOnRefresh){
			this.clearSelection();
		}
		this._lastSelected = null;
		return this.inherited(arguments);
	},
	
	renderArray: function(){
		var grid = this,
			rows = this.inherited(arguments);
		
		Deferred.when(rows, function(rows){
			var selection = grid.selection,
				i, row, selected;
			for(i = 0; i < rows.length; i++){
				row = grid.row(rows[i]);
				selected = row.id in selection ? selection[row.id] : grid.allSelected;
				if(selected){
					grid._select(row, null, selected);
				}
			}
			grid._fireSelectionEvents();
		});
		return rows;
	}
});

});
