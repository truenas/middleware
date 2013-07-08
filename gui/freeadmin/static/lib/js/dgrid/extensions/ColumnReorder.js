define([
	"dojo/_base/lang",
	"dojo/_base/declare",
	"dojo/_base/array",
	"dojo/on",
	"dojo/query",
	"dojo/dnd/Source",
	"put-selector/put",
	"xstyle/css!../css/extensions/ColumnReorder.css"
], function(lang, declare, arrayUtil, on, query, DndSource, put){
	var dndTypeRx = /(\d+)(?:-(\d+))?$/; // used to determine subrow from dndType
	
	// The following 2 functions are used by onDropInternal logic for
	// retrieving/modifying a given subRow.  The `match` variable in each is
	// expected to be the result of executing dndTypeRx on a subRow ID.
	
	function getMatchingSubRow(grid, match) {
		var hasColumnSets = match[2],
			rowOrSet = grid[hasColumnSets ? "columnSets" : "subRows"][match[1]];
		
		return hasColumnSets ? rowOrSet[match[2]] : rowOrSet;
	}
	
	function setMatchingSubRow(grid, match, subRow) {
		if(match[2]){
			grid.columnSets[match[1]][match[2]] = subRow;
		}else{
			grid.subRows[match[1]] = subRow;
		}
	}

	// Builds a prefix for a dndtype value based on a grid id.
	function makeDndTypePrefix(gridId) {
		return "dgrid-" + gridId + '-';
	}

	// Removes the grid id prefix from a dndtype value.  This allows the grid id to contain
	// a dash-number suffix.  This works only if a column is dropped on the grid from which it
	// originated.  Otherwise, a dash-number suffix will cause the regex to match on the wrong values.
	function stripIdPrefix(gridId, dndtype) {
		return dndtype.slice(makeDndTypePrefix(gridId).length);
	}
	
	var ColumnDndSource = declare(DndSource, {
		// summary:
		//		Custom dojo/dnd source extension configured specifically for
		//		dgrid column reordering.
		
		copyState: function(){ return false; }, // never copy
		
		checkAcceptance: function(source, nodes){
			return source == this; // self-accept only
		},
		
		_legalMouseDown: function(evt){
			// Overridden to prevent blocking ColumnResizer resize handles.
			return evt.target.className.indexOf("dgrid-resize-handle") > -1 ? false :
				this.inherited(arguments);
		},
		
		onDropInternal: function(nodes){
			var grid = this.grid,
				match = dndTypeRx.exec(stripIdPrefix(grid.id, nodes[0].getAttribute("dndType"))),
				structureProperty = match[2] ? "columnSets" : "subRows",
				oldSubRow = getMatchingSubRow(grid, match),
				columns = grid.columns;
			
			// First, allow original DnD logic to place node in new location.
			this.inherited(arguments);
			
			if(!match){ return; }
			
			// Then, iterate through the header cells in their new order,
			// to populate a new row array to assign as a new sub-row to the grid.
			// (Wait until the next turn to avoid errors in Opera.)
			setTimeout(function(){
				var newSubRow = arrayUtil.map(nodes[0].parentNode.childNodes, function(col) {
						return columns[col.columnId];
					}),
					eventObject;
				
				setMatchingSubRow(grid, match, newSubRow);
				
				eventObject = {
					grid: grid,
					subRow: newSubRow,
					column: columns[nodes[0].columnId],
					bubbles: true,
					cancelable: true,
					// Set parentType to indicate this is the result of user interaction.
					parentType: "dnd"
				};
				// Set columnSets or subRows depending on which the grid is using.
				eventObject[structureProperty] = grid[structureProperty];
				
				// Emit a custom event which passes the new structure.
				// Allow calling preventDefault() to cancel the reorder operation.
				if(on.emit(grid.domNode, "dgrid-columnreorder", eventObject)){
					// Event was not canceled - force processing of modified structure.
					grid.set(structureProperty, grid[structureProperty]);
				}else{
					// Event was canceled - revert the structure and re-render the header
					// (since the inherited logic invoked above will have shifted cells).
					setMatchingSubRow(grid, match, oldSubRow);
					grid.renderHeader();
					// After re-rendering the header, re-apply the sort arrow if needed.
					if (this._sort && this._sort.length){
						this.updateSortArrow(this._sort);
					}
				}
			}, 0);
		}
	});
	
	var ColumnReorder = declare(null, {
		// summary:
		//		Extension allowing reordering of columns in a grid via drag'n'drop.
		//		Reordering of columns within the same subrow or columnset is also
		//		supported; between different ones is not.
		
		// columnDndConstructor: Function
		//		Constructor to call for instantiating DnD sources within the grid's
		//		header.
		columnDndConstructor: ColumnDndSource,
		
		_initSubRowDnd: function(subRow, dndType){
			// summary:
			//		Initializes a dojo/dnd source for one subrow of a grid;
			//		this could be its only subrow, one of several, or a subrow within a
			//		columnset.
			
			var dndParent, c, len, col, th;
			
			for(c = 0, len = subRow.length; c < len; c++){
				col = subRow[c];
				if(col.reorderable === false){ continue; }
				
				th = col.headerNode;
				if(th.tagName != "TH"){ th = th.parentNode; } // from IE < 8 padding
				// Add dojoDndItem class, and a dndType unique to this subrow.
				put(th, ".dojoDndItem[dndType=" + dndType + "]");
				
				if(!dndParent){ dndParent = th.parentNode; }
			}
			
			if(dndParent){ // (if dndParent wasn't set, no columns are draggable!)
				this._columnDndSources.push(new this.columnDndConstructor(dndParent, {
					horizontal: true,
					grid: this
				}));
			}
		},
		
		renderHeader: function(){
			var dndTypePrefix = makeDndTypePrefix(this.id),
				csLength, cs;
			
			this.inherited(arguments);
			
			// After header is rendered, set up a dnd source on each of its subrows.
			
			this._columnDndSources = [];
			
			if(this.columnSets){
				// Iterate columnsets->subrows->columns.
				for(cs = 0, csLength = this.columnSets.length; cs < csLength; cs++){
					arrayUtil.forEach(this.columnSets[cs], function(subRow, sr){
						this._initSubRowDnd(subRow, dndTypePrefix + cs + "-" + sr);
					}, this);
				}
			}else{
				// Iterate subrows->columns.
				arrayUtil.forEach(this.subRows, function(subRow, sr){
					this._initSubRowDnd(subRow, dndTypePrefix + sr);
				}, this);
			}
		},
		
		_destroyColumns: function(){
			if(this._columnDndSources){
				// Destroy old dnd sources.
				arrayUtil.forEach(this._columnDndSources, function(source){
					source.destroy();
				});
			}
			
			this.inherited(arguments);
		}
	});
	
	ColumnReorder.ColumnDndSource = ColumnDndSource;
	return ColumnReorder;
});
