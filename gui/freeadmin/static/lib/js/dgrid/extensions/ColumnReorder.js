define([
	"dojo/_base/lang",
	"dojo/_base/declare",
	"dojo/_base/array",
	"dojo/query",
	"dojo/dnd/Source",
	"put-selector/put",
	"xstyle/css!../css/extensions/ColumnReorder.css"
], function(lang, declare, arrayUtil, query, DndSource, put){
	var dndTypeRx = /-(\d+)(?:-(\d+))?$/; // used to determine subrow from dndType
	
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
				match = dndTypeRx.exec(nodes[0].getAttribute("dndType")),
				hasColumnSets = !!match[2],
				structure = hasColumnSets ? grid.columnSets : grid.subRows,
				columns = grid.columns,
				newSubRow;
			
			// First, allow original DnD logic to place node in new location.
			this.inherited(arguments);
			
			if(!match){ return; }
			
			// Then, iterate through the header cells in their new order,
			// to populate a new row array to assign as a new sub-row to the grid.
			// (Wait until the next turn to avoid errors in Opera.)
			setTimeout(function(){
				newSubRow = arrayUtil.map(nodes[0].parentNode.childNodes, function(col) {
					return columns[col.columnId];
				});
				
				if(hasColumnSets){
					structure[match[1]][match[2]] = newSubRow;
					grid.set("columnSets", structure);
				}else{
					structure[match[1]] = newSubRow;
					grid.set("subRows", structure);
				}
			}, 0);
		}
	});
	
	var ColumnReorder = declare([], {
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
			var dndTypePrefix = "dgrid-" + this.id + "-",
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
