define(["dojo/_base/declare", "./Selection", "dojo/on", "put-selector/put", "dojo/has"], function(declare, Selection, listen, put, has){
return declare([Selection], {
	// summary:
	//		Add cell level selection capabilities to a grid. The grid will have a selection property and
	//		fire "dgrid-select" and "dgrid-deselect" events.
	
	// ensure we don't select when an individual cell is not identifiable
	selectionDelegate: ".dgrid-cell",
	
	select: function(cell, toCell, value){
		var i, id;
		if(value === undefined){
			// default to true
			value = true;
		}
		if(typeof cell != "object" || !("element" in cell)){
			cell = this.cell(cell);
		}else if(!cell.row){
			// it is row, with the value being a hash
			for(id in value){
				this.select(this.cell(cell.id, id), null, value[id]);
			}
			return;
		}
		if(this.allowSelect(cell)){
			var selection = this.selection,
				rowId = cell.row.id,
				previousRow = selection[rowId];
			if(!cell.column){
				for(i in this.columns){
					this.select(this.cell(rowId, i), null, value);
				}
				return;
			}
			var previous = previousRow && previousRow[cell.column.id];
			if(value === null){
				// indicates a toggle
				value = !previous;
			}
			var element = cell.element;
			previousRow = previousRow || {};
			previousRow[cell.column.id] = value;
			this.selection[rowId] = previousRow;
			
			// Check for all-false objects to see if it can be deleted.
			// This prevents build-up of unnecessary iterations later.
			var hasSelected = false;
			for(i in previousRow){
				if(previousRow[i] === true){
					hasSelected = true;
					break;
				}
			}
			if(!hasSelected){ delete this.selection[rowId]; }
			
			if(element){
				// add or remove classes as appropriate
				if(value){
					put(element, ".dgrid-selected.ui-state-active");
				}else{
					put(element, "!dgrid-selected!ui-state-active");
				}
			}
			if(value != previous && element){
				this._selectionEventQueue(value, "cells").push(cell);
			}
			if(toCell){
				// a range
				if(!toCell.element){
					toCell = this.cell(toCell);
				}
				var toElement = toCell.element;
				var fromElement = cell.element;
				// find if it is earlier or later in the DOM
				var traverser = (toElement && (toElement.compareDocumentPosition ? 
					toElement.compareDocumentPosition(fromElement) == 2 :
					toElement.sourceIndex > fromElement.sourceIndex)) ? "nextSibling" : "previousSibling";
				// now we determine which columns are in the range 
				var idFrom = cell.column.id, idTo = toCell.column.id, started, columnIds = [];
				for(id in this.columns){
					if(started){
						columnIds.push(id);				
					}
					if(id == idFrom && (idFrom = columnIds) || // once found, we mark it off so we don't hit it again
						id == idTo && (idTo = columnIds)){
						columnIds.push(id);
						if(started || // last id, we are done 
							(idFrom == columnIds && id == idTo)){ // the ids are the same, we are done
							break;
						}
						started = true;
					}
				}
				// now we iterate over rows
				var row = cell.row, nextNode = row.element;
				toElement = toCell.row.element;
				do{
					// looping through each row..
					// and now loop through each column to be selected
					for(i = 0; i < columnIds.length; i++){
						cell = this.cell(nextNode, columnIds[i]);
						this.select(cell);
					}
					if(nextNode == toElement){
						break;
					}
				}while((nextNode = cell.row.element[traverser]));
			}
		}
	},
	isSelected: function(object, columnId){
		if(!object){
			return false;
		}
		if(!object.element){
			object = this.cell(object, columnId);
		}

		return this.selection[object.row.id] && !!this.selection[object.row.id][object.column.id];
	},
	clearSelection: function(exceptId){
		// disable exceptId in cell selection, since it would require double parameters
		exceptId = false;
		this.inherited(arguments);
	}
});
});
