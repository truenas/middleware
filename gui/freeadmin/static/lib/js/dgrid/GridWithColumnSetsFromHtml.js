define(["./GridFromHtml", "./ColumnSet", "dojo/_base/declare"],
function(GridFromHtml, ColumnSet, declare){
	// summary:
	//		This module augments GridFromHtml with additional support for interpreting
	//		ColumnSets from colgroups in table markup.
	
	function getColumnSetsFromDom(domNode){
		// summary:
		//		Generates ColumnSets from DOM.
		
		var
			columnsets = [], // to be pushed upon / returned
			cgspans = [], // stores info on columnset sizes (colgroup span)
			rowspans = [], // will store info on any "unexhausted" rowspans
			colgroups = domNode.getElementsByTagName("colgroup"),
			cglen = colgroups.length,
			trs = domNode.getElementsByTagName("tr"),
			trslen = trs.length,
			getNum = GridFromHtml.utils.getNumFromAttr,
			getCol = GridFromHtml.utils.getColumnFromCell,
			// used in loops:
			currcol, // keeps track of what column we're at
			currcg, // and which colgroup
			groupColumns, tr, ths, i, j, tmp;
		
		function incCurrcol(amount){
			// Check whether we've passed into the next colgroup within current row.
			// (Used within th loop)
			currcol += amount;
			tmp = cgspans[currcg];
			if(currcol >= tmp){
				// First, push info for the set we just finished:
				// (i is still the active row index from the for loop)
				columnsets[currcg][i] = groupColumns;
				
				// Now, time to move on to the next columnset for this row.
				currcol -= tmp;
				currcg++;
				groupColumns = [];
			}
		}
		
		// no need for ColumnSet unless there's >1 colgroup
		if(cglen < 2){ return false; }
		
		// read span from each colgroup (defaults to 1)
		for(i = 0; i < cglen; i++){
			// store number of cells this column spans
			tmp = getNum(colgroups[i], "span") || 1;
			cgspans[i] = tmp;
			// add nested array to return value to be populated for this set
			columnsets[i] = [];
			// initialize inner rowspan-tracking array for each
			rowspans[i] = [];
			for(j = 0; j < tmp; j++){
				rowspans[i][j] = 0;
			}
		}
		
		for(i = 0; i < trslen; i++){
			currcol = currcg = 0;
			groupColumns = [];
			tr = trs[i];
			ths = tr.getElementsByTagName("th"), thslen = ths.length;
			for(j = 0; j < thslen; j++){
				// account for space occupied by previous rowSpans
				while(rowspans[currcg][currcol]){
					// decrement rowspan "leftover" for next iteration
					rowspans[currcg][currcol]--;
					// skip past this cell for now, and try again w/ updated currcg/col
					incCurrcol(1);
				}
				
				// store cell info
				tmp = getCol(ths[j]);
				groupColumns.push(tmp);
				
				// if this cell has rowspan, keep that in mind for future iterations
				rowspans[currcg][currcol] = tmp.rowSpan ? tmp.rowSpan - 1 : 0;
				
				// increment currcol/currcg appropriately, accounting for cell colSpan
				incCurrcol(tmp.colSpan || 1);
			}
			// At the end of processing each row, there is a chance that the last
			// column set didn't get pushed yet (specifically if there are trailing
			// rowspans - since rowspan "debt" gets iterated at the beginning of each
			// iteration, not the end).  In that case, push the last one now.
			if(groupColumns.length){
				columnsets[currcg][i] = groupColumns;
			}
		}
		if(tr){
			domNode.removeChild(tr.parentNode);
		}
		return columnsets;
	}
	return declare([GridFromHtml, ColumnSet], {
		configStructure: function(){
			// summary:
			//		Configure subRows based on HTML originally in srcNodeRef
			
			var tmp;
			if(!this._checkedTrs){
				tmp = getColumnSetsFromDom(this.srcNodeRef);
				if(tmp){
					this.columnSets = tmp;
					this._checkedTrs = true;
				}else{
					// no reason to worry about ColumnSets, let GridFromHtml do the job
					return this.inherited(arguments);
				}
			}
			return this.inherited(arguments);
		}
	});
});