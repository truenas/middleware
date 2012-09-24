define(["dojo/_base/declare", "dojo/on", "dojo/query", "dojo/_base/lang", "dojo/dom", "dojo/dom-geometry", "dojo/has", "../util/misc", "put-selector/put", "dojo/_base/html", "xstyle/css!../css/extensions/ColumnResizer.css"],
function(declare, listen, query, lang, dom, geom, has, miscUtil, put){

var hasPointFromNode = has("touch") && webkitConvertPointFromNodeToPage;

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

return declare([], {
	resizeNode: null,
	minWidth: 40,	//minimum column width in px
	gridWidth: null, //place holder for the grid width property
	_resizedColumns: false, //flag that indicates if resizer has converted column widths to px
	
	resizeColumnWidth: function(colId, width){
		// Summary:
		//      calls grid's styleColumn function to add a style for the column
		// colId: String
		//      column id
		// width: Integer
		//      new width of the column

		// Keep track of old styles so we don't get a long list in the stylesheet
		
		// don't react to widths <= 0, e.g. for hidden columns
		if(width <= 0){ return; }
		
		var old = this._columnStyles[colId],
			x = this.styleColumn(colId, "width: " + width + "px;");
		
		old && old.remove();
		
		// keep a reference for future removal
		this._columnStyles[colId] = x;
	},
	
	configStructure: function(){
		// Reset and remove column styles when a new structure is set
		this._resizedColumns = false;
		for(var name in this._columnStyles){
			this._columnStyles[name].remove();
		}
		this._columnStyles = {};

		this.inherited(arguments);
	},
	renderHeader: function(){
		this.inherited(arguments);
		
		var grid = this;
		grid.gridWidth = grid.headerNode.clientWidth - 1; //for some reason, total column width needs to be 1 less than this

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

			if(!col){ continue; }

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
			grid.mouseMoveListen = listen.pausable(document.body,
				"mousemove" + (has("touch") ? ",touchmove" : ""),
				miscUtil.throttleDelayed(function(e){ grid._updateResizerPosition(e); })
			);
			grid.mouseUpListen = listen.pausable(document.body,
				"mouseup" + (has("touch") ? ",touchend" : ""),
				function(e){
					grid._resizeMouseUp(e);
					grid.mouseMoveListen.pause();
					grid.mouseUpListen.pause();
				}
			);
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
		var grid = this;
		grid._startX = grid._getResizeMouseLocation(e); //position of the target
		
		// Grab the position of the grid within the body;  will be used to place the resizer in the correct place
		// Since geom.position returns an incorrect "x" value (due to mobile zoom and getBoundingClientRect()),
		// webkitConvertPointFromNodeToPage and WebKitPoint will provide a more accurate point
		grid._gridX = hasPointFromNode ? 
						webkitConvertPointFromNodeToPage(grid.bodyNode, new WebKitPoint(0, 0)).x : 
						geom.position(grid.bodyNode).x;
						
		grid._targetCell = query(".dgrid-column-" + target.columnId, grid.headerNode)[0];

		// show resizer
		if(!grid._resizer){
			grid._resizer = put(grid.domNode, "div.dgrid-column-resizer");
		}

		grid._resizer.style.display = "block";
		grid._updateResizerPosition(e);
	},
	_resizeMouseUp: function(e){
		// Summary:
		//      called when mouse button is released
		// e: Object
		//      mouseup event object

		this._readyToResize = false;

		//This is used to set all the column widths to a static size
		if(!this._resizedColumns){
			var colNodes = query(".dgrid-cell", this.headerNode);

			if(this.columnSets && this.columnSets.length){
				colNodes = colNodes.filter(function(node){
					var idx = node.columnId.split("-");
					return idx[0] == "0";
				});
			}else if(this.subRows && this.subRows.length > 1){
				colNodes = colNodes.filter(function(node){
					return node.columnId.charAt(0) == "0";
				});
			}

			// Get a set of sizes before we start mutating, to avoid
			// weird disproportionate measures if the grid has set
			// column widths, but no full grid width set
			var colSizes = colNodes.map(function(colNode){
				return colNode.offsetWidth;
			});

			// Set a baseline size for each column based on
			// its original measure
			colNodes.forEach(function(colNode, i){
				this.resizeColumnWidth(colNode.columnId, colSizes[i]);
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

		if(cell.columnId != lastCol){
			if(totalWidth + delta < this.gridWidth) {
				//need to set last column's width to auto
				this.styleColumn(lastCol, "width: auto;");
			}else if(lastColWidth-delta <= this.minWidth) {
				//change last col width back to px, unless it is the last column itself being resized...
				this.resizeColumnWidth(lastCol, this.minWidth);
			}
		}
		if(newWidth < this.minWidth){
			//enforce minimum widths
			newWidth = this.minWidth;
		}

		this.resizeColumnWidth(cell.columnId, newWidth);
		this.resize();
		this._hideResizer();
	},
	_updateResizerPosition: function(e){
		// Summary:
		//      updates position of resizer bar as mouse moves
		// e: Object
		//      mousemove event object

		var mousePos = this._getResizeMouseLocation(e),
			delta = mousePos - this._startX, //change from where user clicked to where they drag
			cell = this._targetCell,
			left = mousePos - this._gridX;
		if(cell.offsetWidth + delta < this.minWidth){ 
			left = this._startX - this._gridX - (cell.offsetWidth - this.minWidth); 
		}
		this._resizer.style.left = left  + "px";
	},

	_hideResizer: function(){
		// Summary:
		//      sets resizer bar display to none
		this._resizer.style.display = "none";
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
