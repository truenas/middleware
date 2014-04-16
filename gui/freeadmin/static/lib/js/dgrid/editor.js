define([
	"dojo/_base/kernel",
	"dojo/_base/lang",
	"dojo/_base/array",
	"dojo/_base/Deferred",
	"dojo/on",
	"dojo/aspect",
	"dojo/has",
	"dojo/query",
	"./Grid",
	"put-selector/put",
	"dojo/_base/sniff"
], function(kernel, lang, arrayUtil, Deferred, on, aspect, has, query, Grid, put){

// Variables to track info for cell currently being edited
// (active* variables are for editOn editors only)
var activeCell, activeValue, activeOptions, focusedCell;

function updateInputValue(input, value){
	// common code for updating value of a standard input
	input.value = value;
	if(input.type == "radio" || input.type == "checkbox"){
		input.checked = input.defaultChecked = !!value;
	}
}

function dataFromValue(value, oldValue){
	// Default logic for translating values from editors;
	// tries to preserve type if possible.
	if(typeof oldValue == "number"){
		value = isNaN(value) ? value : parseFloat(value);
	}else if(typeof oldValue == "boolean"){
		value = value == "true" ? true : value == "false" ? false : value;
	}else if(oldValue instanceof Date){
		var asDate = new Date(value);
		value = isNaN(asDate.getTime()) ? value : asDate;
	}
	return value;
}

// intermediary frontend to dataFromValue for HTML and widget editors
function dataFromEditor(column, cmp){
	if(typeof cmp.get == "function"){ // widget
		return dataFromValue(cmp.get("value"));
	}else{ // HTML input
		return dataFromValue(
			cmp[cmp.type == "checkbox" || cmp.type == "radio"  ? "checked" : "value"]);
	}
}

function setProperty(grid, cell, oldValue, value, triggerEvent){
	// Updates dirty hash and fires dgrid-datachange event for a changed value.
	var cellElement, row, column, eventObject;
	// test whether old and new values are inequal, with coercion (e.g. for Dates)
	if((oldValue && oldValue.valueOf()) != (value && value.valueOf())){
		cellElement = cell.element;
		row = cell.row;
		column = cell.column;
		if(column.field && row){
			// TODO: remove rowId in lieu of cell (or grid.row/grid.cell)
			// (keeping for the moment for back-compat, but will note in changes)
			eventObject = {
				grid: grid,
				cell: cell,
				rowId: row.id,
				oldValue: oldValue,
				value: value,
				bubbles: true,
				cancelable: true
			};
			if(triggerEvent && triggerEvent.type){
				eventObject.parentType = triggerEvent.type;
			}
			
			if(on.emit(cellElement, "dgrid-datachange", eventObject)){
				if(grid.updateDirty){
					// for OnDemandGrid: update dirty data, and save if autoSave is true
					grid.updateDirty(row.id, column.field, value);
					// perform auto-save (if applicable) in next tick to avoid
					// unintentional mishaps due to order of handler execution
					column.autoSave && setTimeout(function(){ grid._trackError("save"); }, 0);
				}else{
					// update store-less grid
					row.data[column.field] = value;
				}
			}else{
				// Otherwise keep the value the same
				// For the sake of always-on editors, need to manually reset the value
				var cmp;
				if((cmp = cellElement.widget)){
					// set _dgridIgnoreChange to prevent an infinite loop in the
					// onChange handler and prevent dgrid-datachange from firing
					// a second time
					cmp._dgridIgnoreChange = true;
					cmp.set("value", oldValue);
					setTimeout(function(){ cmp._dgridIgnoreChange = false; }, 0);
				}else if((cmp = cellElement.input)){
					updateInputValue(cmp, oldValue);
				}
				
				return oldValue;
			}
		}
	}
	return value;
}

// intermediary frontend to setProperty for HTML and widget editors
function setPropertyFromEditor(grid, cmp, triggerEvent) {
	var cell = grid.cell(cmp.domNode || cmp),
		column = cell.column,
		value,
		id,
		editedRow;
	
	if(!cmp.isValid || cmp.isValid()){
		value = setProperty(grid, cell,
			activeCell ? activeValue : cmp._dgridLastValue,
			dataFromEditor(column, cmp), triggerEvent);
		
		if(activeCell){ // for editors with editOn defined
			activeValue = value;
		}else{ // for always-on editors, update _dgridLastValue immediately
			cmp._dgridLastValue = value;
		}

		if(cmp.type === "radio" && cmp.name && !column.editOn && column.field){
			editedRow = grid.row(cmp);
			
			// Update all other rendered radio buttons in the group
			query("input[type=radio][name=" + cmp.name + "]", grid.contentNode).forEach(function(radioBtn){
				var row = grid.row(radioBtn);
				// Only update _dgridLastValue and the dirty data if it exists
				// and is not already false
				if(radioBtn !== cmp && radioBtn._dgridLastValue){
					radioBtn._dgridLastValue = false;
					if(grid.updateDirty){
						grid.updateDirty(row.id, column.field, false);
					}else{
						// update store-less grid
						row.data[column.field] = false;
					}
				}
			});
			
			// Also update dirty data for rows that are not currently rendered
			for(id in grid.dirty){
				if(editedRow.id !== id && grid.dirty[id][column.field]){
					grid.updateDirty(id, column.field, false);
				}
			}
		}
	}
}

// editor creation/hookup/placement logic

function createEditor(column){
	// Creates an editor instance based on column definition properties,
	// and hooks up events.
	var editor = column.editor,
		editOn = column.editOn,
		grid = column.grid,
		isWidget = typeof editor != "string", // string == standard HTML input
		args, cmp, node, putstr, handleChange;
	
	args = column.editorArgs || {};
	if(typeof args == "function"){ args = args.call(grid, column); }
	
	if(isWidget){
		cmp = new editor(args);
		node = cmp.focusNode || cmp.domNode;
		
		// Add dgrid-input to className to make consistent with HTML inputs.
		node.className += " dgrid-input";
		
		// For editOn editors, connect to onBlur rather than onChange, since
		// the latter is delayed by setTimeouts in Dijit and will fire too late.
		cmp.connect(cmp, editOn ? "onBlur" : "onChange", function(){
			if(!cmp._dgridIgnoreChange){
				setPropertyFromEditor(grid, this, {type: "widget"});
			}
		});
	}else{
		handleChange = function(evt){
			var target = evt.target;
			if("_dgridLastValue" in target && target.className.indexOf("dgrid-input") > -1){
				setPropertyFromEditor(grid, target, evt);
			}
		};

		// considerations for standard HTML form elements
		if(!column.grid._hasInputListener){
			// register one listener at the top level that receives events delegated
			grid._hasInputListener = true;
			grid.on("change", function(evt){ handleChange(evt); });
			// also register a focus listener
		}
		
		putstr = editor == "textarea" ? "textarea" :
			"input[type=" + editor + "]";
		cmp = node = put(putstr + ".dgrid-input", lang.mixin({
			name: column.field,
			tabIndex: isNaN(column.tabIndex) ? -1 : column.tabIndex
		}, args));
		
		if(has("ie") < 9 || (has("ie") && has("quirks"))){
			// IE<9 / quirks doesn't fire change events for all the right things,
			// and it doesn't bubble.
			if(editor == "radio" || editor == "checkbox"){
				// listen for clicks since IE doesn't fire change events properly for checks/radios
				on(cmp, "click", function(evt){ handleChange(evt); });
			}else{
				on(cmp, "change", function(evt){ handleChange(evt); });
			}
		}
	}
	
	return cmp;
}

function createSharedEditor(column, originalRenderCell){
	// Creates an editor instance with additional considerations for
	// shared usage across an entire column (for columns with editOn specified).
	
	var cmp = createEditor(column),
		grid = column.grid,
		isWidget = cmp.domNode,
		node = cmp.domNode || cmp,
		focusNode = cmp.focusNode || node,
		reset = isWidget ?
			function(){ cmp.set("value", cmp._dgridLastValue); } :
			function(){
				updateInputValue(cmp, cmp._dgridLastValue);
				// call setProperty again in case we need to revert a previous change
				setPropertyFromEditor(column.grid, cmp);
			},
		keyHandle;
	
	function blur(){
		var element = activeCell;
		focusNode.blur();
		
		if(typeof grid.focus === "function"){
			// Dijit form widgets don't end up dismissed until the next turn,
			// so wait before calling focus (otherwise Keyboard will focus the
			// input again).  IE<9 needs to wait longer, otherwise the cell loses
			// focus after we've set it.
			setTimeout(function(){
				grid.focus(element);
			}, isWidget && has("ie") < 9 ? 15 : 0);
		}
	}
	
	function onblur(){
		var parentNode = node.parentNode,
			i = parentNode.children.length - 1,
			options = { alreadyHooked: true },
			cell = grid.cell(node);
		
		// emit an event immediately prior to removing an editOn editor
		on.emit(cell.element, "dgrid-editor-hide", {
			grid: grid,
			cell: cell,
			column: column,
			editor: cmp,
			bubbles: true,
			cancelable: false
		});
		column._editorBlurHandle.pause();
		// Remove the editor from the cell, to be reused later.
		parentNode.removeChild(node);
		
		put(cell.element, "!dgrid-cell-editing");
		
		// Clear out the rest of the cell's contents, then re-render with new value.
		while(i--){ put(parentNode.firstChild, "!"); }
		Grid.appendIfNode(parentNode, column.renderCell(
			column.grid.row(parentNode).data, activeValue, parentNode,
			activeOptions ? lang.delegate(options, activeOptions) : options));
		
		// Reset state now that editor is deactivated;
		// reset focusedCell as well since some browsers will not trigger the
		// focusout event handler in this case
		activeCell = activeValue = activeOptions = focusedCell = null;
	}
	
	function dismissOnKey(evt){
		// Contains logic for reacting to enter/escape keypresses to save/cancel edits.
		// Calls `focusNode.blur()` in cases where field should be dismissed.
		var key = evt.keyCode || evt.which;
		
		if(key == 27){ // escape: revert + dismiss
			reset();
			activeValue = cmp._dgridLastValue;
			blur();
		}else if(key == 13 && column.dismissOnEnter !== false){ // enter: dismiss
			// FIXME: Opera is "reverting" even in this case
			blur();
		}
	}
	
	// hook up enter/esc key handling
	keyHandle = on(focusNode, "keydown", dismissOnKey);
	
	// hook up blur handler, but don't activate until widget is activated
	(column._editorBlurHandle = on.pausable(cmp, "blur", onblur)).pause();
	
	return cmp;
}

function showEditor(cmp, column, cellElement, value){
	// Places a shared editor into the newly-active cell in the column.
	// Also called when rendering an editor in an "always-on" editor column.
	
	var isWidget = cmp.domNode,
		grid = column.grid;
	
	// for regular inputs, we can update the value before even showing it
	if(!isWidget){ updateInputValue(cmp, value); }
	
	cellElement.innerHTML = "";
	put(cellElement, ".dgrid-cell-editing");
	put(cellElement, cmp.domNode || cmp);
	
	if(isWidget){
		// For widgets, ensure startup is called before setting value,
		// to maximize compatibility with flaky widgets like dijit/form/Select.
		if(!cmp._started){ cmp.startup(); }
		
		// Set value, but ensure it isn't processed as a user-generated change.
		// (Clear flag on a timeout to wait for delayed onChange to fire first)
		cmp._dgridIgnoreChange = true;
		cmp.set("value", value);
		setTimeout(function(){ cmp._dgridIgnoreChange = false; }, 0);
	}
	// track previous value for short-circuiting or in case we need to revert
	cmp._dgridLastValue = value;
	// if this is an editor with editOn, also update activeValue
	// (activeOptions will have been updated previously)
	if(activeCell){ 
		activeValue = value; 
		// emit an event immediately prior to placing a shared editor
		on.emit(cellElement, "dgrid-editor-show", {
			grid: grid,
			cell: grid.cell(cellElement),
			column: column,
			editor: cmp,
			bubbles: true,
			cancelable: false
		});
	}
}

function edit(cell) {
	// summary:
	//		Method to be mixed into grid instances, which will show/focus the
	//		editor for a given grid cell.  Also used by renderCell.
	// cell: Object
	//		Cell (or something resolvable by grid.cell) to activate editor on.
	// returns:
	//		If the cell is editable, returns a promise resolving to the editor
	//		input/widget when the cell editor is focused.
	//		If the cell is not editable, returns null.
	
	var row, column, cellElement, dirty, field, value, cmp, dfd;
	
	if(!cell.column){ cell = this.cell(cell); }
	if(!cell || !cell.element){ return null; }
	
	column = cell.column;
	field = column.field;
	cellElement = cell.element.contents || cell.element;
	
	if((cmp = column.editorInstance)){ // shared editor (editOn used)
		if(activeCell != cellElement){
			// get the cell value
			row = cell.row;
			dirty = this.dirty && this.dirty[row.id];
			value = (dirty && field in dirty) ? dirty[field] :
				column.get ? column.get(row.data) : row.data[field];
			// check to see if the cell can be edited
			if(!column.canEdit || column.canEdit(cell.row.data, value)){
				activeCell = cellElement;

				showEditor(column.editorInstance, column, cellElement, value);

				// focus / blur-handler-resume logic is surrounded in a setTimeout
				// to play nice with Keyboard's dgrid-cellfocusin as an editOn event
				dfd = new Deferred();
				setTimeout(function(){
					// focus the newly-placed control (supported by form widgets and HTML inputs)
					if(cmp.focus){ cmp.focus(); }
					// resume blur handler once editor is focused
					if(column._editorBlurHandle){ column._editorBlurHandle.resume(); }
					dfd.resolve(cmp);
				}, 0);

				return dfd.promise;
			}
		}

	}else if(column.editor){ // editor but not shared; always-on
		cmp = cellElement.widget || cellElement.input;
		if(cmp){
			dfd = new Deferred();
			if(cmp.focus){ cmp.focus(); }
			dfd.resolve(cmp);
			return dfd.promise;
		}
	}
	return null;
}

// editor column plugin function

return function(column, editor, editOn){
	// summary:
	//		Adds editing capability to a column's cells.
	
	var originalRenderCell = column.renderCell || Grid.defaultRenderCell,
		listeners = [],
		isWidget;
	
	function commonInit(column) {
		// Common initialization logic for both editOn and always-on editors
		var grid = column.grid,
			focusoutHandle;
		if(!grid.edit){
			// Only perform this logic once on a given grid
			grid.edit = edit;
			
			listeners.push(on(grid.domNode, '.dgrid-input:focusin', function () {
				focusedCell = grid.cell(this);
			}));
			focusoutHandle = grid._editorFocusoutHandle =
				on.pausable(grid.domNode, '.dgrid-input:focusout', function () {
					focusedCell = null;
				});
			listeners.push(focusoutHandle);
			
			listeners.push(aspect.before(grid, 'removeRow', function (row) {
				row = grid.row(row);
				if (focusedCell && focusedCell.row.id === row.id) {
					// Pause the focusout handler until after this row has had
					// time to re-render, if this removal is part of an update.
					// A setTimeout is used here instead of resuming in the
					// insertRow aspect below, since if a row were actually
					// removed (not updated) while editing, the handler would
					// not be properly hooked up again for future occurrences.
					focusoutHandle.pause();
					setTimeout(function () {
						focusoutHandle.resume();
					}, 0);
				}
			}));
			listeners.push(aspect.after(grid, 'insertRow', function (rowElement) {
				var row = grid.row(rowElement);
				if (focusedCell && focusedCell.row.id === row.id) {
					grid.edit(grid.cell(row, focusedCell.column.id));
				}
				return rowElement;
			}));
		}
	}

	if(!column){ column = {}; }
	
	// accept arguments as parameters to editor function, or from column def,
	// but normalize to column def.
	column.editor = editor = editor || column.editor || "text";
	column.editOn = editOn = editOn || column.editOn;
	
	isWidget = typeof editor != "string";
	
	// warn for widgetArgs -> editorArgs; TODO: remove @ 0.4
	if(column.widgetArgs){
		kernel.deprecated("column.widgetArgs", "use column.editorArgs instead",
			"dgrid 0.4");
		column.editorArgs = column.widgetArgs;
	}
	
	aspect.after(column, "init", editOn ? function(){
		commonInit(column);
		// Create one shared widget/input to be swapped into the active cell.
		column.editorInstance = createSharedEditor(column, originalRenderCell);
	} : function(){
		var grid = column.grid;
		commonInit(column);
		
		if(isWidget){
			// add advice for cleaning up widgets in this column
			listeners.push(aspect.before(grid, "removeRow", function(rowElement){
				// destroy our widget during the row removal operation,
				// but don't trip over loading nodes from incomplete requests
				var cellElement = grid.cell(rowElement, column.id).element,
					widget = cellElement && (cellElement.contents || cellElement).widget;
				if(widget){
					grid._editorFocusoutHandle.pause();
					widget.destroyRecursive();
				}
			}));
		}
	});
	
	aspect.after(column, "destroy", function(){
		arrayUtil.forEach(listeners, function(l){ l.remove(); });
		if(column._editorBlurHandle){ column._editorBlurHandle.remove(); }
		
		if(editOn && isWidget){ column.editorInstance.destroyRecursive(); }
		
		// Remove the edit function, so that it (and other one-time listeners)
		// will be re-added if editor columns are re-initialized
		column.grid.edit = null;
	});
	
	column.renderCell = editOn ? function(object, value, cell, options){
		// TODO: Consider using event delegation
		// (Would require using dgrid's focus events for activating on focus,
		// which we already advocate in README for optimal use)
		
		if(!options || !options.alreadyHooked){
			// in IE<8, cell is the child of the td due to the extra padding node
			on(cell.tagName == "TD" ? cell : cell.parentNode, editOn, function(){
				activeOptions = options;
				column.grid.edit(this);
			});
		}
		
		// initially render content in non-edit mode
		return originalRenderCell.call(column, object, value, cell, options);
		
	} : function(object, value, cell, options){
		// always-on: create editor immediately upon rendering each cell
		if(!column.canEdit || column.canEdit(object, value)){
			var cmp = createEditor(column);
			showEditor(cmp, column, cell, value);
			// Maintain reference for later use.
			cell[isWidget ? "widget" : "input"] = cmp;
		}else{
			return originalRenderCell.call(column, object, value, cell, options);
		}
	};
	
	return column;
};
});
