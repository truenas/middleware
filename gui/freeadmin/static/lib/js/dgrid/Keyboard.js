define([
	"dojo/_base/declare",
	"dojo/aspect",
	"dojo/on",
	"dojo/_base/lang",
	"dojo/has",
	"put-selector/put",
	"dojo/_base/Deferred",
	"dojo/_base/sniff"
], function(declare, aspect, on, lang, has, put, Deferred){

var delegatingInputTypes = {
		checkbox: 1,
		radio: 1,
		button: 1
	},
	hasGridCellClass = /\bdgrid-cell\b/,
	hasGridRowClass = /\bdgrid-row\b/;

has.add("dom-contains", function(global, doc, element){
	return !!element.contains; // not supported by FF < 9
});

function contains(parent, node){
	// summary:
	//		Checks to see if an element is contained by another element.
	
	if(has("dom-contains")){
		return parent.contains(node);
	}else{
		return parent.compareDocumentPosition(node) & 8 /* DOCUMENT_POSITION_CONTAINS */;
	}
}

var Keyboard = declare(null, {
	// summary:
	//		Adds keyboard navigation capability to a list or grid.
	
	// pageSkip: Number
	//		Number of rows to jump by when page up or page down is pressed.
	pageSkip: 10,
	
	tabIndex: 0,
	
	// keyMap: Object
	//		Hash which maps key codes to functions to be executed (in the context
	//		of the instance) for key events within the grid's body.
	keyMap: null,
	
	// headerKeyMap: Object
	//		Hash which maps key codes to functions to be executed (in the context
	//		of the instance) for key events within the grid's header row.
	headerKeyMap: null,
	
	postMixInProperties: function(){
		this.inherited(arguments);
		
		if(!this.keyMap){
			this.keyMap = lang.mixin({}, Keyboard.defaultKeyMap);
		}
		if(!this.headerKeyMap){
			this.headerKeyMap = lang.mixin({}, Keyboard.defaultHeaderKeyMap);
		}
	},
	
	postCreate: function(){
		this.inherited(arguments);
		var grid = this;
		
		function handledEvent(event){
			// text boxes and other inputs that can use direction keys should be ignored and not affect cell/row navigation
			var target = event.target;
			return target.type && (!delegatingInputTypes[target.type] || event.keyCode == 32);
		}
		
		function enableNavigation(areaNode){
			var cellNavigation = grid.cellNavigation,
				isFocusableClass = cellNavigation ? hasGridCellClass : hasGridRowClass,
				isHeader = areaNode === grid.headerNode,
				initialNode = areaNode;
			
			function initHeader(){
				grid._focusedHeaderNode = initialNode =
					cellNavigation ? grid.headerNode.getElementsByTagName("th")[0] : grid.headerNode;
				if(initialNode){ initialNode.tabIndex = grid.tabIndex; }
			}
			
			if(isHeader){
				// Initialize header now (since it's already been rendered),
				// and aspect after future renderHeader calls to reset focus.
				initHeader();
				aspect.after(grid, "renderHeader", initHeader, true);
			}else{
				aspect.after(grid, "renderArray", function(ret){
					// summary:
					//		Ensures the first element of a grid is always keyboard selectable after data has been
					//		retrieved if there is not already a valid focused element.
					
					return Deferred.when(ret, function(ret){
						var focusedNode = grid._focusedNode || initialNode;
						
						// do not update the focused element if we already have a valid one
						if(isFocusableClass.test(focusedNode.className) && contains(areaNode, focusedNode)){
							return ret;
						}
						
						// ensure that the focused element is actually a grid cell, not a
						// dgrid-preload or dgrid-content element, which should not be focusable,
						// even when data is loaded asynchronously
						for(var i = 0, elements = areaNode.getElementsByTagName("*"), element; (element = elements[i]); ++i){
							if(isFocusableClass.test(element.className)){
								focusedNode = grid._focusedNode = element;
								break;
							}
						}
						
						focusedNode.tabIndex = grid.tabIndex;
						return ret;
					});
				});
			}
			
			grid._listeners.push(on(areaNode, "mousedown", function(event){
				if(!handledEvent(event)){
					grid._focusOnNode(event.target, isHeader, event);
				}
			}));
			
			grid._listeners.push(on(areaNode, "keydown", function(event){
				// For now, don't squash browser-specific functionalities by letting
				// ALT and META function as they would natively
				if(event.metaKey || event.altKey) {
					return;
				}
				
				var handler = grid[isHeader ? "headerKeyMap" : "keyMap"][event.keyCode];
				
				// Text boxes and other inputs that can use direction keys should be ignored and not affect cell/row navigation
				if(handler && !handledEvent(event)){
					handler.call(grid, event);
				}
			}));
		}
		
		if(this.tabableHeader){
			enableNavigation(this.headerNode);
			on(this.headerNode, "dgrid-cellfocusin", function(){
				grid.scrollTo({ x: this.scrollLeft });
			});
		}
		enableNavigation(this.contentNode);
	},
	
	addKeyHandler: function(key, callback, isHeader){
		// summary:
		//		Adds a handler to the keyMap on the instance.
		//		Supports binding additional handlers to already-mapped keys.
		// key: Number
		//		Key code representing the key to be handled.
		// callback: Function
		//		Callback to be executed (in instance context) when the key is pressed.
		// isHeader: Boolean
		//		Whether the handler is to be added for the grid body (false, default)
		//		or the header (true).
		
		// Aspects may be about 10% slower than using an array-based appraoch,
		// but there is significantly less code involved (here and above).
		return aspect.after( // Handle
			this[isHeader ? "headerKeyMap" : "keyMap"], key, callback, true);
	},
	
	_focusOnNode: function(element, isHeader, event){
		var focusedNodeProperty = "_focused" + (isHeader ? "Header" : "") + "Node",
			focusedNode = this[focusedNodeProperty],
			cellOrRowType = this.cellNavigation ? "cell" : "row",
			cell = this[cellOrRowType](element),
			inputs,
			input,
			numInputs,
			inputFocused,
			i;
		
		element = cell && cell.element;
		if(!element){ return; }
		
		if(this.cellNavigation){
			inputs = element.getElementsByTagName("input");
			for(i = 0, numInputs = inputs.length; i < numInputs; i++){
				input = inputs[i];
				if((input.tabIndex != -1 || "lastValue" in input) && !input.disabled){
					// Employ workaround for focus rectangle in IE < 8
					if(has("ie") < 8){ input.style.position = "relative"; }
					input.focus();
					if(has("ie") < 8){ input.style.position = ""; }
					inputFocused = true;
					break;
				}
			}
		}
		
		event = lang.mixin({ grid: this }, event);
		if(event.type){
			event.parentType = event.type;
		}
		if(!event.bubbles){
			// IE doesn't always have a bubbles property already true.
			// Opera throws if you try to set it to true if it is already true.
			event.bubbles = true;
		}
		if(focusedNode){
			// Clean up previously-focused element
			// Remove the class name and the tabIndex attribute
			put(focusedNode, "!dgrid-focus[!tabIndex]");
			if(has("ie") < 8){
				// Clean up after workaround below (for non-input cases)
				focusedNode.style.position = "";
			}
			
			// Expose object representing focused cell or row losing focus, via
			// event.cell or event.row; which is set depends on cellNavigation.
			event[cellOrRowType] = this[cellOrRowType](focusedNode);
			on.emit(element, "dgrid-cellfocusout", event);
		}
		focusedNode = this[focusedNodeProperty] = element;
		
		// Expose object representing focused cell or row gaining focus, via
		// event.cell or event.row; which is set depends on cellNavigation.
		// Note that yes, the same event object is being reused; on.emit
		// performs a shallow copy of properties into a new event object.
		event[cellOrRowType] = cell;
		
		if(!inputFocused){
			if(has("ie") < 8){
				// setting the position to relative magically makes the outline
				// work properly for focusing later on with old IE.
				// (can't be done a priori with CSS or screws up the entire table)
				element.style.position = "relative";
			}
			element.tabIndex = this.tabIndex;
			element.focus();
		}
		put(element, ".dgrid-focus");
		on.emit(focusedNode, "dgrid-cellfocusin", event);
	},
	
	focusHeader: function(element){
		this._focusOnNode(element || this._focusedHeaderNode, true);
	},
	
	focus: function(element){
		this._focusOnNode(element || this._focusedNode, false);
	}
});

// Common functions used in default keyMap (called in instance context)

var moveFocusVertical = Keyboard.moveFocusVertical = function(event, steps){
	var cellNavigation = this.cellNavigation,
		target = this[cellNavigation ? "cell" : "row"](event),
		columnId = cellNavigation && target.column.id,
		next = this.down(this._focusedNode, steps, true);
	
	// Navigate within same column if cell navigation is enabled
	if(cellNavigation){ next = this.cell(next, columnId); }
	this._focusOnNode(next, false, event);
	
	event.preventDefault();
};

var moveFocusUp = Keyboard.moveFocusUp = function(event){
	moveFocusVertical.call(this, event, -1);
};

var moveFocusDown = Keyboard.moveFocusDown = function(event){
	moveFocusVertical.call(this, event, 1);
};

var moveFocusPageUp = Keyboard.moveFocusPageUp = function(event){
	moveFocusVertical.call(this, event, -this.pageSkip);
};

var moveFocusPageDown = Keyboard.moveFocusPageDown = function(event){
	moveFocusVertical.call(this, event, this.pageSkip);
};

var moveFocusHorizontal = Keyboard.moveFocusHorizontal = function(event, steps){
	if(!this.cellNavigation){ return; }
	var isHeader = !this.row(event), // header reports row as undefined
		currentNode = this["_focused" + (isHeader ? "Header" : "") + "Node"];
	
	this._focusOnNode(this.right(currentNode, steps), isHeader, event);
	event.preventDefault();
};

var moveFocusLeft = Keyboard.moveFocusLeft = function(event){
	moveFocusHorizontal.call(this, event, -1);
};

var moveFocusRight = Keyboard.moveFocusRight = function(event){
	moveFocusHorizontal.call(this, event, 1);
};

var moveHeaderFocusEnd = Keyboard.moveHeaderFocusEnd = function(event, scrollToBeginning){
	// Header case is always simple, since all rows/cells are present
	var nodes;
	if(this.cellNavigation){
		nodes = this.headerNode.getElementsByTagName("th");
		this._focusOnNode(nodes[scrollToBeginning ? 0 : nodes.length - 1], true, event);
	}
	// In row-navigation mode, there's nothing to do - only one row in header
	
	// Prevent browser from scrolling entire page
	event.preventDefault();
};

var moveHeaderFocusHome = Keyboard.moveHeaderFocusHome = function(event){
	moveHeaderFocusEnd.call(this, event, true);
};

var moveFocusEnd = Keyboard.moveFocusEnd = function(event, scrollToTop){
	// summary:
	//		Handles requests to scroll to the beginning or end of the grid.
	
	// Assume scrolling to top unless event is specifically for End key
	var self = this,
		cellNavigation = this.cellNavigation,
		contentNode = this.contentNode,
		contentPos = scrollToTop ? 0 : contentNode.scrollHeight,
		scrollPos = contentNode.scrollTop + contentPos,
		endChild = contentNode[scrollToTop ? "firstChild" : "lastChild"],
		hasPreload = endChild.className.indexOf("dgrid-preload") > -1,
		endTarget = hasPreload ? endChild[(scrollToTop ? "next" : "previous") + "Sibling"] : endChild,
		endPos = endTarget.offsetTop + (scrollToTop ? 0 : endTarget.offsetHeight),
		handle;
	
	if(hasPreload){
		// Find the nearest dgrid-row to the relevant end of the grid
		while(endTarget && endTarget.className.indexOf("dgrid-row") < 0){
			endTarget = endTarget[(scrollToTop ? "next" : "previous") + "Sibling"];
		}
		// If none is found, there are no rows, and nothing to navigate
		if(!endTarget){ return; }
	}
	
	// Grid content may be lazy-loaded, so check if content needs to be
	// loaded first
	if(!hasPreload || endChild.offsetHeight < 1){
		// End row is loaded; focus the first/last row/cell now
		if(cellNavigation){
			// Preserve column that was currently focused
			endTarget = this.cell(endTarget, this.cell(event).column.id);
		}
		this._focusOnNode(endTarget, false, event);
	}else{
		// In IE < 9, the event member references will become invalid by the time
		// _focusOnNode is called, so make a (shallow) copy up-front
		if(!has("dom-addeventlistener")){
			event = lang.mixin({}, event);
		}
		
		// If the topmost/bottommost row rendered doesn't reach the top/bottom of
		// the contentNode, we are using OnDemandList and need to wait for more
		// data to render, then focus the first/last row in the new content.
		handle = aspect.after(this, "renderArray", function(rows){
			handle.remove();
			return Deferred.when(rows, function(rows){
				var target = rows[scrollToTop ? 0 : rows.length - 1];
				if(cellNavigation){
					// Preserve column that was currently focused
					target = self.cell(target, self.cell(event).column.id);
				}
				self._focusOnNode(target, false, event);
			});
		});
	}
	
	if(scrollPos === endPos){
		// Grid body is already scrolled to end; prevent browser from scrolling
		// entire page instead
		event.preventDefault();
	}
};

var moveFocusHome = Keyboard.moveFocusHome = function(event){
	moveFocusEnd.call(this, event, true);
};

function preventDefault(event){
	event.preventDefault();
}

Keyboard.defaultKeyMap = {
	32: preventDefault, // space
	33: moveFocusPageUp, // page up
	34: moveFocusPageDown, // page down
	35: moveFocusEnd, // end
	36: moveFocusHome, // home
	37: moveFocusLeft, // left
	38: moveFocusUp, // up
	39: moveFocusRight, // right
	40: moveFocusDown // down
};

// Header needs fewer default bindings (no vertical), so bind it separately
Keyboard.defaultHeaderKeyMap = {
	32: preventDefault, // space
	35: moveHeaderFocusEnd, // end
	36: moveHeaderFocusHome, // home
	37: moveFocusLeft, // left
	39: moveFocusRight // right
};

return Keyboard;
});