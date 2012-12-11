define(["dojo/_base/kernel", "dojo/_base/array", "dojo/on", "dojo/aspect", "dojo/_base/sniff", "put-selector/put"],
function(kernel, arrayUtil, on, aspect, has, put){
	return function(column, type){
		
		var listeners = [],
			grid, headerCheckbox;
		
		if(!column){ column = {}; }
		
		if(column.type){
			column.selectorType = column.type;
			kernel.deprecated("columndef.type", "use columndef.selectorType instead", "dgrid 1.0");
		}
		// accept type as argument to Selector function, or from column def
		column.selectorType = type = type || column.selectorType || "checkbox";
		column.sortable = false;
		
		function changeInput(value){
			// creates a function that modifies the input on an event
			return function(event){
				var rows = event.rows,
					len = rows.length,
					state = "false",
					selection, mixed, i;
				
				for(i = 0; i < len; i++){
					var element = grid.cell(rows[i], column.id).element;
					if(!element){ continue; } // skip if row has been entirely removed
					element = (element.contents || element).input;
					if(!element.disabled){
						// only change the value if it is not disabled
						element.checked = value;
						element.setAttribute("aria-checked", value);
					}
				}
				if(headerCheckbox.type == "checkbox"){
					selection = grid.selection;
					mixed = false;
					// see if the header checkbox needs to be indeterminate
					for(i in selection){
						// if there is anything in the selection, than it is indeterminate
						if(selection[i] != grid.allSelected){
							mixed = true;
							break;
						}
					}
					headerCheckbox.indeterminate = mixed;
					headerCheckbox.checked = grid.allSelected;
					if (mixed) {
						state = "mixed";
					} else if (grid.allSelected) {
						state = "true";
					}
					headerCheckbox.setAttribute("aria-checked", state);
				}
			};
		}
		
		function onSelect(event){
			// we would really only care about click, since other input sources, like spacebar
			// trigger a click, but the click event doesn't provide access to the shift key in firefox, so
			// listen for keydown's as well to get an event in firefox that we can properly retrieve
			// the shiftKey property from
			if(event.type == "click" || event.keyCode == 32 || (!has("opera") && event.keyCode == 13) || event.keyCode === 0){
				var row = grid.row(event),
					lastRow = grid._lastSelected && grid.row(grid._lastSelected);
				grid._selectionTriggerEvent = event;
				
				if(type == "radio"){
					if(!lastRow || lastRow.id != row.id){
						grid.clearSelection();
						grid.select(row, null, true);
						grid._lastSelected = row.element;
					}
				}else{
					if(row){
						if(event.shiftKey){
							// make sure the last input always ends up checked for shift key 
							changeInput(true)({rows: [row]});
						}else{
							// no shift key, so no range selection
							lastRow = null;
						}
						lastRow = event.shiftKey ? lastRow : null;
						grid.select(lastRow || row, row, lastRow ? undefined : null);
						grid._lastSelected = row.element;
					}else{
						// No row resolved; must be the select-all checkbox.
						put(this, (grid.allSelected ? "!" : ".") + "dgrid-select-all");
						grid[grid.allSelected ? "clearSelection" : "selectAll"]();
					}
				}
				grid._selectionTriggerEvent = null;
			}
		}
		
		function setupSelectionEvents(){
			// register one listener at the top level that receives events delegated
			grid._hasSelectorInputListener = true;
			listeners.push(aspect.before(grid, "_initSelectionEvents", function(){
				// listen for clicks and keydown as the triggers
				this.on(".dgrid-selector:click,.dgrid-selector:keydown", onSelect);
			}));
			var handleSelect = grid._handleSelect;
			grid._handleSelect = function(event){
				// ignore the default select handler for events that originate from the selector column
				if(this.cell(event).column != column){
					handleSelect.apply(this, arguments);
				}
			};
			if(typeof column.disabled == "function"){
				// we override this method to have selections follow the disabled method for selectability
				var originalAllowSelect = grid.allowSelect;
				grid.allowSelect = function(row){
					return originalAllowSelect.call(this, row) && !column.disabled(row.data);
				};
			}
			// register listeners to the select and deselect events to change the input checked value
			listeners.push(grid.on("dgrid-select", changeInput(true)));
			listeners.push(grid.on("dgrid-deselect", changeInput(false)));
		}
		
		var disabled = column.disabled;
		var renderInput = typeof type == "function" ? type : function(value, cell, object){
			var parent = cell.parentNode;
			// must set the class name on the outer cell in IE for keystrokes to be intercepted
			put(parent && parent.contents ? parent : cell, ".dgrid-selector");
			var input = cell.input || (cell.input = put(cell, "input[type="+type + "]", {
				tabIndex: isNaN(column.tabIndex) ? -1 : column.tabIndex,
				disabled: disabled && (typeof disabled == "function" ? disabled(object) : disabled),
				checked: value
			}));
			input.setAttribute("aria-checked", !!value);
			
			if(!grid._hasSelectorInputListener){
				setupSelectionEvents();
			}
			
			return input;
		};
		
		aspect.after(column, "init", function(){
			grid = column.grid;
		});
		
		aspect.after(column, "destroy", function(){
			arrayUtil.forEach(listeners, function(l){ l.remove(); });
			grid._hasSelectorInputListener = false;
		});
		
		column.renderCell = function(object, value, cell, options, header){
			var row = object && grid.row(object);
			value = row && grid.selection[row.id];
			renderInput(value, cell, object);
		};
		column.renderHeaderCell = function(th){
			var label = column.label || column.field || "";
			
			if(type == "radio" || !grid.allowSelectAll){
				th.appendChild(document.createTextNode(label));
				if(!grid._hasSelectorInputListener){
					setupSelectionEvents();
				}
			}else{
				renderInput(false, th, {});
			}
			headerCheckbox = th.lastChild;
		};
		
		return column;
	};
});
