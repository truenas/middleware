define(["dojo/_base/declare", "dojo/on", "dojo/query", "dojo/_base/lang", "dojo/dom", "dojo/dom-geometry", "dojo/has", "../util/misc", "put-selector/put", "dojo/_base/html", "xstyle/css!../css/extensions/ColumnResizer.css"],
function(declare, listen, query, lang, dom, geom, has, miscUtil, put){

function addRowSpan(table, span, startRow, column, id){
	// loop through the rows of the table and add this column's id to
	// the rows' column
	for(var i=1; i<span; i++){
		table[startRow+i][column] = id;
	}
}
function subRowAssoc(subRows){
	// Take a sub-row structure and output an object with key=>value pairs
	// The keys will be the column id's; the values will be the first-row column
	// that column's resizer should be associated with.

	var i = subRows.length,
		l = i,
		numCols = subRows[0].length,
		table = new Array(i);

	// create table-like structure in an array so it can be populated
	// with row-spans and col-spans
	while(i--){
		table[i] = new Array(numCols);
	}

	var associations = {};

	for(i=0; i<l; i++){
		var row = table[i],
			subRow = subRows[i];

		// j: counter for table columns
		// js: counter for subrow structure columns
		for(var j=0, js=0; j<numCols; j++){
			var cell = subRow[js], k;

			// if something already exists in the table (row-span), skip this
			// spot and go to the next
			if(typeof row[j] != "undefined"){
				continue;
			}
			row[j] = cell.id;

			if(cell.rowSpan && cell.rowSpan > 1){
				addRowSpan(table, cell.rowSpan, i, j, cell.id);
			}

			// colSpans are only applicable in the second or greater rows
			// and only if the colSpan is greater than 1
			if(i>0 && cell.colSpan && cell.colSpan > 1){
				for(k=1; k<cell.colSpan; k++){
					// increment j and assign the id since this is a span
					row[++j] = cell.id;
					if(cell.rowSpan && cell.rowSpan > 1){
						addRowSpan(table, cell.rowSpan, i, j, cell.id);
					}
				}
			}
			associations[cell.id] = subRows[0][j].id;
			js++;
		}
	}

	return associations;
}

function resizeColumnWidth(grid, colId, width, parentType){
	// don't react to widths <= 0, e.g. for hidden columns
	if(width <= 0){ return; }

	var column = grid.columns[colId],
		event = {
			grid: grid,
			columnId: colId,
			width: width,
			bubbles: true,
			cancelable: true
		},
		rule;
	
	if(parentType){
		event.parentType = parentType;
	}
	
	if(!grid._resizedColumns || listen.emit(grid.headerNode, "dgrid-columnresize", event)){
		// Update width on column object, then convert value for CSS
		if(width === "auto"){
			delete column.width;
		}else{
			column.width = width;
			width += "px";
		}
		
		rule = grid._columnSizes[colId];
		
		if(rule){
			// Modify existing, rather than deleting + adding
			rule.set("width", width);
		}else{
			// Use miscUtil function directly, since we clean these up ourselves anyway
			rule = miscUtil.addCssRule(
				"#" + miscUtil.escapeCssIdentifier(grid.domNode.id) + " .dgrid-column-" + colId, "width: " + width + ";");
		}

		// keep a reference for future removal
		grid._columnSizes[colId] = rule;
		grid.resize();
		return true;
	}
}

// Functions for shared resizer node

var resizerNode, // DOM node for resize indicator, reused between instances
	resizableCount = 0; // Number of ColumnResizer-enabled grid instances
var resizer = {
	// This object contains functions for manipulating the shared resizerNode
	create: function(){
		resizerNode = put("div.dgrid-column-resizer");
	},
	destroy: function(){
		put(resizerNode, "!");
		resizerNode = null;
	},
	show: function(grid){
		var pos = geom.position(grid.domNode, true);
		resizerNode.style.top = pos.y + "px";
		resizerNode.style.height = pos.h + "px";
		put(document.body, resizerNode);
	},
	move: function(x){
		resizerNode.style.left = x + "px";
	},
	hide: function(){
		resizerNode.parentNode.removeChild(resizerNode);
	}
};

return declare(null, {
	resizeNode: null,
	
	// minWidth: Number
	//		Minimum column width, in px.
	minWidth: 40,
	
	// adjustLastColumn: Boolean
	//		If true, adjusts the last column's width to "auto" at times where the
	//		browser would otherwise stretch all columns to span the grid.
	adjustLastColumn: true,
	
	_resizedColumns: false, // flag indicating if resizer has converted column widths to px
	
	buildRendering: function(){
		this.inherited(arguments);
		
		// Create resizerNode when first grid w/ ColumnResizer is created
		if(!resizableCount++){
			resizer.create();
		}
	},
	
	destroy: function(){
		this.inherited(arguments);
		
		// Remove any applied column size styles since we're tracking them directly
		for(var name in this._columnSizes){
			this._columnSizes[name].remove();
		}
		
		// If this is the last grid on the page with ColumnResizer, destroy the
		// shared resizerNode
		if(!--resizableCount){
			resizer.destroy();
		}
	},
	
	resizeColumnWidth: function(colId, width){
		// Summary:
		//      calls grid's styleColumn function to add a style for the column
		// colId: String
		//      column id
		// width: Integer
		//      new width of the column
		return resizeColumnWidth(this, colId, width);
	},
	
	configStructure: function(){
		var oldSizes = this._oldColumnSizes = lang.mixin({}, this._columnSizes), // shallow clone
			k;
		
		this._resizedColumns = false;
		this._columnSizes = {};
		
		this.inherited(arguments);
		
		// Remove old column styles that are no longer relevant; this is specifically
		// done *after* calling inherited so that _columnSizes will contain keys
		// for all columns in the new structure that were assigned widths.
		for(k in oldSizes){
			if(!(k in this._columnSizes)){
				oldSizes[k].remove();
			}
		}
		delete this._oldColumnSizes;
	},
	
	_configColumn: function(column){
		this.inherited(arguments);
		
		var colId = column.id,
			rule;
		
		if("width" in column){
			// Update or add a style rule for the specified width
			if((rule = this._oldColumnSizes[colId])){
				rule.set("width", column.width + "px");
			}else{
				rule = miscUtil.addCssRule(
					"#" + this.domNode.id + " .dgrid-column-" + colId, "width: " + column.width + "px;");
			}
			this._columnSizes[colId] = rule;
		}
	},
	
	renderHeader: function(){
		this.inherited(arguments);
		
		var grid = this;
		
		var assoc;
		if(this.columnSets && this.columnSets.length){
			var csi = this.columnSets.length;
			while(csi--){
				assoc = lang.mixin(assoc||{}, subRowAssoc(this.columnSets[csi]));
			}
		}else if(this.subRows && this.subRows.length > 1){
			assoc = subRowAssoc(this.subRows);
		}

		var colNodes = query(".dgrid-cell", grid.headerNode),
			i = colNodes.length;
		while(i--){
			var colNode = colNodes[i],
				id = colNode.columnId,
				col = grid.columns[id],
				childNodes = colNode.childNodes;

			if(!col || col.resizable === false){ continue; }

			var headerTextNode = put("div.dgrid-resize-header-container");
			colNode.contents = headerTextNode;

			// move all the children to the header text node
			while(childNodes.length > 0){
				put(headerTextNode, childNodes[0]);
			}

			put(colNode, headerTextNode, "div.dgrid-resize-handle.resizeNode-"+id).columnId = 
				assoc ? assoc[id] : id;
		}

		if(!grid.mouseMoveListen){
			// establish listeners for initiating, dragging, and finishing resize
			listen(grid.headerNode,
				".dgrid-resize-handle:mousedown" +
					(has("touch") ? ",.dgrid-resize-handle:touchstart" : ""),
				function(e){
					grid._resizeMouseDown(e, this);
					grid.mouseMoveListen.resume();
					grid.mouseUpListen.resume();
				}
			);
			grid._listeners.push(grid.mouseMoveListen = listen.pausable(document,
				"mousemove" + (has("touch") ? ",touchmove" : ""),
				miscUtil.throttleDelayed(function(e){ grid._updateResizerPosition(e); })
			));
			grid._listeners.push(grid.mouseUpListen = listen.pausable(document,
				"mouseup" + (has("touch") ? ",touchend" : ""),
				function(e){
					grid._resizeMouseUp(e);
					grid.mouseMoveListen.pause();
					grid.mouseUpListen.pause();
				}
			));
			// initially pause the move/up listeners until a drag happens
			grid.mouseMoveListen.pause();
			grid.mouseUpListen.pause();
		}
	}, // end renderHeader

	_resizeMouseDown: function(e, target){
		// Summary:
		//      called when mouse button is pressed on the header
		// e: Object
		//      mousedown event object
		
		// preventDefault actually seems to be enough to prevent browser selection
		// in all but IE < 9.  setSelectable works for those.
		e.preventDefault();
		dom.setSelectable(this.domNode, false);
		this._startX = this._getResizeMouseLocation(e); //position of the target
		
		this._targetCell = query(".dgrid-column-" + target.columnId, this.headerNode)[0];

		// Show resizerNode after initializing its x position
		this._updateResizerPosition(e);
		resizer.show(this);
	},
	_resizeMouseUp: function(e){
		// Summary:
		//      called when mouse button is released
		// e: Object
		//      mouseup event object
		
		var columnSizes = this._columnSizes,
			colNodes, colWidths, gridWidth;
		
		if(this.adjustLastColumn){
			// For some reason, total column width needs to be 1 less than this
			gridWidth = this.headerNode.clientWidth - 1;
		}
		
		//This is used to set all the column widths to a static size
		if(!this._resizedColumns){
			colNodes = query(".dgrid-cell", this.headerNode);
			
			if(this.columnSets && this.columnSets.length){
				colNodes = colNodes.filter(function(node){
					var idx = node.columnId.split("-");
					return idx[0] == "0" && !(node.columnId in columnSizes);
				});
			}else if(this.subRows && this.subRows.length > 1){
				colNodes = colNodes.filter(function(node){
					return node.columnId.charAt(0) == "0" && !(node.columnId in columnSizes);
				});
			}
			
			// Get a set of sizes before we start mutating, to avoid
			// weird disproportionate measures if the grid has set
			// column widths, but no full grid width set
			colWidths = colNodes.map(function(colNode){
				return colNode.offsetWidth;
			});
			
			// Set a baseline size for each column based on
			// its original measure
			colNodes.forEach(function(colNode, i){
				this.resizeColumnWidth(colNode.columnId, colWidths[i]);
			}, this);
			
			this._resizedColumns = true;
		}
		dom.setSelectable(this.domNode, true);
		
		var cell = this._targetCell,
			delta = this._getResizeMouseLocation(e) - this._startX, //final change in position of resizer
			newWidth = cell.offsetWidth + delta, //the new width after resize
			obj = this._getResizedColumnWidths(),//get current total column widths before resize
			totalWidth = obj.totalWidth,
			lastCol = obj.lastColId,
			lastColWidth = query(".dgrid-column-"+lastCol, this.headerNode)[0].offsetWidth;
		
		if(newWidth < this.minWidth){
			//enforce minimum widths
			newWidth = this.minWidth;
		}
		
		if(resizeColumnWidth(this, cell.columnId, newWidth, e.type)){
			if(cell.columnId != lastCol && this.adjustLastColumn){
				if(totalWidth + delta < gridWidth) {
					//need to set last column's width to auto
					resizeColumnWidth(this, lastCol, "auto", e.type);
				}else if(lastColWidth-delta <= this.minWidth) {
					//change last col width back to px, unless it is the last column itself being resized...
					resizeColumnWidth(this, lastCol, this.minWidth, e.type);
				}
			}
		}
		resizer.hide();
		
		// Clean up after the resize operation
		delete this._startX;
		delete this._targetCell;
	},
	
	_updateResizerPosition: function(e){
		// Summary:
		//      updates position of resizer bar as mouse moves
		// e: Object
		//      mousemove event object

		if(!this._targetCell){ return; } // Release event was already processed
		
		var mousePos = this._getResizeMouseLocation(e),
			delta = mousePos - this._startX, //change from where user clicked to where they drag
			width = this._targetCell.offsetWidth,
			left = mousePos;
		if(width + delta < this.minWidth){ 
			left = this._startX - (width - this.minWidth); 
		}
		resizer.move(left);
	},

	_getResizeMouseLocation: function(e){
		//Summary:
		//      returns position of mouse relative to the left edge
		// e: event object
		//      mouse move event object
		var posX = 0;
		if(e.pageX){
			posX = e.pageX;
		}else if(e.clientX){
			posX = e.clientX + document.body.scrollLeft +
				document.documentElement.scrollLeft;
		}
		return posX;
	},
	_getResizedColumnWidths: function (){
		//Summary:
		//      returns object containing new column width and column id
		var totalWidth = 0,
			colNodes = query(".dgrid-cell", this.headerNode);

		// For ColumnSets and subRows, only the top row of columns matters
		if(this.columnSets && this.columnSets.length){
			colNodes = colNodes.filter(function(node){
				var idx = node.columnId.split("-");
				return idx[1] == "0";
			});
		}else if(this.subRows && this.subRows.length > 1){
			colNodes = colNodes.filter(function(node){
				return node.columnId.charAt(0) == "0";
			});
		}

		var i = colNodes.length;
		if(!i){ return {}; }

		var lastColId = colNodes[i-1].columnId;

		while(i--){
			totalWidth += colNodes[i].offsetWidth;
		}
		return {totalWidth: totalWidth, lastColId: lastColId};
	}
});
});
