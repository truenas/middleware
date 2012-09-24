define([
	"dojo/_base/declare",
	"dojo/aspect",
	"dojo/on",
	"./List",
	"dojo/_base/lang",
	"dojo/has",
	"put-selector/put",
	"dojo/_base/Deferred",
	"dojo/_base/sniff"
], function(declare, aspect, on, List, lang, has, put, Deferred){

var delegatingInputTypes = {
		checkbox: 1,
		radio: 1,
		button: 1
	},
	hasGridCellClass = /\bdgrid-cell\b/,
	hasGridRowClass = /\bdgrid-row\b/;

has.add("dom-contains", function(){
	return !!document.createElement("a").contains;
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

return declare([List], {
	// summary:
	// 		Add keyboard navigation capability to a grid/list
	pageSkip: 10,
	tabIndex: 0,
	
	postCreate: function(){
		this.inherited(arguments);
		var grid = this;
		
		function handledEvent(event){
			// text boxes and other inputs that can use direction keys should be ignored and not affect cell/row navigation
			var target = event.target;
			return target.type && (!delegatingInputTypes[target.type] || event.keyCode == 32);
		}
		
		function navigateArea(areaNode){
			var isFocusableClass = grid.cellNavigation ? hasGridCellClass : hasGridRowClass,
				cellFocusedElement = areaNode,
				next;
			
			function focusOnCell(element, event, dontFocus){
				var cell = grid[grid.cellNavigation ? "cell" : "row"](element);
				
				element = cell && cell.element;
				if(!element){ return; }
				
				if(!event.bubbles){
					// IE doesn't always have a bubbles property already true, Opera will throw an error if you try to set it to true if it is already true
					event.bubbles = true;
				}
				// clean up previously-focused element
				// remove the class name and the tabIndex attribute
				put(cellFocusedElement, "!dgrid-focus[!tabIndex]");
				if(cellFocusedElement){
					if(has("ie") < 8){
						// clean up after workaround below (for non-input cases)
						cellFocusedElement.style.position = "";
					}
					event.cell = cellFocusedElement;
					on.emit(element, "dgrid-cellfocusout", event);
				}
				cellFocusedElement = element;
				event.cell = element;
				if(!dontFocus){
					if(has("ie") < 8){
						// setting the position to relative magically makes the outline
						// work properly for focusing later on with old IE.
						// (can't be done a priori with CSS or screws up the entire table)
						element.style.position = "relative";
					}
					element.tabIndex = grid.tabIndex;
					element.focus();
				}
				put(element, ".dgrid-focus");
				on.emit(cellFocusedElement, "dgrid-cellfocusin", lang.mixin({ parentType: event.type }, event));
			}
			
			while((next = cellFocusedElement.firstChild) && !isFocusableClass.test(next.className)){
				cellFocusedElement = next;
			}
			if(next){ cellFocusedElement = next; }
			
			if(areaNode === grid.contentNode){
				aspect.after(grid, "renderArray", function(ret){
					// summary:
					//		Ensures the first element of a grid is always keyboard selectable after data has been
					//		retrieved if there is not already a valid focused element.
					
					return Deferred.when(ret, function(ret){
						// do not update the focused element if we already have a valid one
						if(isFocusableClass.test(cellFocusedElement.className) && contains(areaNode, cellFocusedElement)){
							return ret;
						}
						
						// ensure that the focused element is actually a grid cell, not a
						// dgrid-preload or dgrid-content element, which should not be focusable,
						// even when data is loaded asynchronously
						for(var i = 0, elements = areaNode.getElementsByTagName("*"), element; (element = elements[i]); ++i){
							if(isFocusableClass.test(element.className)){
								cellFocusedElement = element;
								break;
							}
						}
						
						cellFocusedElement.tabIndex = grid.tabIndex;
						
						return ret;
					});
				});
			}else if(isFocusableClass.test(cellFocusedElement.className)){
				cellFocusedElement.tabIndex = grid.tabIndex;
			}
			
			on(areaNode, "mousedown", function(event){
				if(!handledEvent(event)){
					focusOnCell(event.target, event);
				}
			});
			
			on(areaNode, "keydown", function(event){
				// For now, don't squash browser-specific functionalities by letting
				// ALT and META function as they would natively
				if(event.metaKey || event.altKey) {
					return;
				}
				
				var focusedElement = event.target;
				var keyCode = event.keyCode;
				if(handledEvent(event)){
					// text boxes and other inputs that can use direction keys should be ignored and not affect cell/row navigation
					return;
				}
				var move = {
					32: 0, // space bar
					33: -grid.pageSkip, // page up
					34: grid.pageSkip,// page down
					37: -1, // left
					38: -1, // up
					39: 1, // right
					40: 1, // down
					35: 10000, //end
					36: -10000 // home
				}[keyCode];
				if(isNaN(move)){
					return;
				}
				var nextSibling, columnId, cell = grid.cell(cellFocusedElement);
				var orientation;
				if(keyCode == 37 || keyCode == 39){
					// horizontal movement (left and right keys)
					if(!grid.cellNavigation){
						return; // do nothing for row-only navigation
					}
					orientation = "right";
				}else{
					// other keys are vertical
					orientation = "down";
					columnId = cell && cell.column && cell.column.id;
					cell = grid.row(cellFocusedElement);
				}
				if(move){
					cell = cell && grid[orientation](cell, move, true);
				}
				var nextFocus = cell && cell.element;
				if(nextFocus){
					if(columnId){
						nextFocus = grid.cell(nextFocus, columnId).element;
					}
					if(grid.cellNavigation){
						var inputs = nextFocus.getElementsByTagName("input");
						var inputFocused;
						for(var i = 0;i < inputs.length; i++){
							var input = inputs[i];
							if((input.tabIndex != -1 || "lastValue" in input) && !input.disabled){
								// focusing here requires the same workaround for IE<8,
								// though here we can get away with doing it all at once.
								if(has("ie") < 8){ input.style.position = "relative"; }
								input.focus();
								if(has("ie") < 8){ input.style.position = ""; }
								inputFocused = true;
								break;
							}
						}
					}
					focusOnCell(nextFocus, event, inputFocused);
				}
				event.preventDefault();
			});
			
			return function(target){
				target = target || cellFocusedElement;
				focusOnCell(target, { target: target });
			}
		}
		
		if(this.tabableHeader){
			this.focusHeader = navigateArea(this.headerNode);
		}
		
		this.focus = navigateArea(this.contentNode);
	}
});
});
