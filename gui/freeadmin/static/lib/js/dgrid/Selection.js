define(["dojo/_base/kernel", "dojo/_base/declare", "dojo/_base/Deferred", "dojo/on", "dojo/has", "dojo/aspect", "./List", "dojo/has!touch?./util/touch", "put-selector/put", "dojo/query"],
function(kernel, declare, Deferred, on, has, aspect, List, touchUtil, put){

var ctrlEquiv = has("mac") ? "metaKey" : "ctrlKey";
return declare([List], {
	// summary:
	//		Add selection capabilities to a grid. The grid will have a selection property and
	//		fire "dgrid-select" and "dgrid-deselect" events.
	
	// selectionDelegate: String
	//		Selector to delegate to as target of selection events.
	selectionDelegate: ".dgrid-row",
	
	// selectionEvents: String
	//		Event (or events, comma-delimited) to listen on to trigger select logic.
	//		Note: this is ignored in the case of touch devices.
	selectionEvents: "mousedown,mouseup,dgrid-cellfocusin",
	
	// deselectOnRefresh: Boolean
	//		If true, the selection object will be cleared when refresh is called.
	deselectOnRefresh: true,
	
	//allowSelectAll: Boolean
	//		If true, allow ctrl/cmd+A to select all rows.
	//		Also consulted by the selector plugin for showing select-all checkbox.
	allowSelectAll: false,
	
	create: function(){
		this.selection = {};
		return this.inherited(arguments);
	},
	postCreate: function(){
		this.inherited(arguments);
		this._initSelectionEvents(); // first time; set up event hooks
	},
	
	// selection:
	//		An object where the property names correspond to 
	//		object ids and values are true or false depending on whether an item is selected
	selection: {},
	// selectionMode: String
	//		The selection mode to use, can be "none", "multiple", "single", or "extended".
	selectionMode: "extended",
	
	_setSelectionMode: function(mode){
		// summary:
		//		Updates selectionMode, resetting necessary variables.
		if(mode == this.selectionMode){ return; } // prevent unnecessary spinning
		
		// Start selection fresh when switching mode.
		this.clearSelection();
		this._lastSelected = null;
		
		this.selectionMode = mode;
	},
	setSelectionMode: function(mode){
		kernel.deprecated("setSelectionMode(...)", 'use set("selectionMode", ...) instead', "dgrid 1.0");
		this.set("selectionMode", mode);
	},
	
	_handleSelect: function(event, currentTarget){
		// don't run if selection mode is none,
		// or if coming from a dgrid-cellfocusin from a mousedown
		if(this.selectionMode == "none" ||
				(event.type == "dgrid-cellfocusin" && event.parentType == "mousedown") ||
				(event.type == "mouseup" && currentTarget != this._waitForMouseUp)){
			return;
		}
		this._waitForMouseUp = null;

		var ctrlKey = !event.keyCode ? event[ctrlEquiv] : event.ctrlKey;
		if(!event.keyCode || !event.ctrlKey || event.keyCode == 32){
			var mode = this.selectionMode,
				row = currentTarget,
				rowObj = this.row(row),
				lastRow = this._lastSelected;
			
			if(mode == "single"){
				if(lastRow == row){
					if(ctrlKey){
						// allow deselection even within single select mode
						this.select(row, null, null);
					}
				}else{
					this.clearSelection();
					this.select(row);
				}
				this._lastSelected = row;
			}else if(this.selection[rowObj.id] && !event.shiftKey && event.type == "mousedown"){
				// we wait for the mouse up if we are clicking a selected item so that drag n' drop
				// is possible without losing our selection
				this._waitForMouseUp = row;
			}else{
				var value;
				// clear selection first for non-ctrl-clicks in extended mode,
				// as well as for right-clicks on unselected targets
				if((event.button != 2 && mode == "extended" && !ctrlKey) ||
						(event.button == 2 && !(this.selection[rowObj.id]))){
					this.clearSelection(rowObj.id, true);
				}
				if(!event.shiftKey){
					// null == toggle; undefined == true;
					lastRow = value = ctrlKey ? null : undefined;
				}
				this.select(row, lastRow, value);

				if(!lastRow){
					// update lastRow reference for potential subsequent shift+select
					// (current row was already selected by earlier logic)
					this._lastSelected = row;
				}
			}
			if(!event.keyCode && (event.shiftKey || ctrlKey)){
				// prevent selection in firefox
				event.preventDefault();
			}
		}
	},

	_initSelectionEvents: function(){
		// summary:
		//		Performs first-time hookup of event handlers containing logic
		//		required for selection to operate.
		
		var grid = this,
			selector = this.selectionDelegate;
		
		// This is to stop IE8+'s web accelerator and selection.
		// It also stops selection in Chrome/Safari.
		on(this.domNode, "selectstart", function(event){
			// In IE, this also bubbles from text selection inside editor fields;
			// we don't want to prevent that!
			var tag = event.target && event.target.tagName;
			if(tag != "INPUT" && tag != "TEXTAREA"){
				event.preventDefault();
			}
		});
		
		function focus(event){
			grid._handleSelect(event, this);
		}
		
		if(touchUtil){
			// listen for touch taps if available
			on(this.contentNode, touchUtil.selector(selector, touchUtil.tap), function(evt){
				grid._handleSelect(evt, this);
			});
		}else{
			// listen for actions that should cause selections
			on(this.contentNode, on.selector(selector, this.selectionEvents), focus);
		}

		// If allowSelectAll is true, allow ctrl/cmd+A to (de)select all rows.
		// (Handler further checks against _allowSelectAll, which may be updated
		// if selectionMode is changed post-init.)
		if(this.allowSelectAll){
			this.on("keydown", function(event) {
				if (event[ctrlEquiv] && event.keyCode == 65) {
					event.preventDefault();
					grid[grid.allSelected ? "clearSelection" : "selectAll"]();
				}
			});
		}
		
		aspect.before(this, "removeRow", function(rowElement, justCleanup){
			var row;
			if(!justCleanup){
				row = this.row(rowElement);
				// if it is a real row removal for a selected item, deselect it
				if(row && (row.id in this.selection)){ this.deselect(rowElement); }
			}
		});
	},
	
	allowSelect: function(row){
		// summary:
		//		A method that can be overriden to determine whether or not a row (or 
		//		cell) can be selected. By default, all rows (or cells) are selectable.
		return true;
	},
	
	_selectionEventQueue: function(value, type){
		var grid = this,
			event = "dgrid-" + (value ? "select" : "deselect"),
			rows = this[event]; // current event queue (actually cells for CellSelection)
		
		if(rows){ return rows; } // return existing queue, allowing to push more
		
		// Create a timeout to fire an event for the accumulated rows once everything is done.
		// We expose the callback in case the event needs to be fired immediately.
		setTimeout(this._fireSelectionEvent = function(){
			if(!rows){ return; } // rows will be set only the first time this is called
			
			var eventObject = {
				bubbles: true,
				grid: grid
			};
			eventObject[type] = rows;
			on.emit(grid.contentNode, event, eventObject);
			rows = null;
			// clear the queue, so we create a new one as needed
			delete grid[event];
		}, 0);
		return (rows = this[event] = []);
	},
	select: function(row, toRow, value){
		if(value === undefined){
			// default to true
			value = true;
		} 
		if(!row.element){
			row = this.row(row);
		}
		if(this.allowSelect(row)){
			var selection = this.selection;
			var previousValue = selection[row.id];
			if(value === null){
				// indicates a toggle
				value = !previousValue;
			}
			var element = row.element;
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
			if(value != previousValue && element){
				// add to the queue of row events
				this._selectionEventQueue(value, "rows").push(row);
			}
			
			if(toRow){
				if(!toRow.element){
					toRow = this.row(toRow);
				}
				var toElement = toRow.element;
				var fromElement = row.element;
				// find if it is earlier or later in the DOM
				var traverser = (toElement && (toElement.compareDocumentPosition ? 
					toElement.compareDocumentPosition(fromElement) == 2 :
					toElement.sourceIndex > fromElement.sourceIndex)) ? "down" : "up";
				while(row.element != toElement && (row = this[traverser](row))){
					this.select(row);
				}
			}
		}
	},
	deselect: function(row, toRow){
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
				this.deselect(id);
			}
		}
		if(!dontResetLastSelected){
			this._lastSelected = null;
		}
	},
	selectAll: function(){
		this.allSelected = true;
		this.selection = {}; // we do this to clear out pages from previous sorts
		for(var i in this._rowIdToObject){
			var row = this.row(this._rowIdToObject[i]);
			this.select(row.id);
		}
	},
	isSelected: function(object){
		if(!object){
			return false;
		}
		if(!object.element){
			object = this.row(object);
		}

		return !!this.selection[object.id];
	},
	
	refresh: function(){
		if(this.deselectOnRefresh){
			this.clearSelection();
			// Need to fire the selection event now because after the refresh,
			// the nodes that we will fire for will be gone.
			this._fireSelectionEvent && this._fireSelectionEvent();
		}
		this._lastSelected = null;
		this.inherited(arguments);
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
					grid.select(row, null, selected);
				}
			}
		});
		return rows;
	}
});

});
