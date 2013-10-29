define([
	"dojo/_base/lang",
	"dojo/_base/declare",
	"dgrid/util/misc",
	"xstyle/css!../css/extensions/CompoundColumns.css"
], function(lang, declare, miscUtil){
	return declare(null, {
		// summary:
		//		Extension allowing for specification of columns with additional
		//		header rows spanning multiple columns for strictly display purposes.
		//		Only works on `columns` arrays, not `columns` objects or `subRows`
		//		(nor ColumnSets).
		// description:
		//		CompoundColumns allows nested header cell configurations, wherein the
		//		higher-level headers may span multiple columns and are for
		//		display purposes only.
		//		These nested header cells are configured using a special recursive
		//		`children` property in the column definition, where only the deepest
		//		children are ultimately rendered in the grid as actual columns.
		//		In addition, the deepest child columns may be rendered without
		//		individual headers by specifying `showChildHeaders: false` on the parent.
		
		configStructure: function(){
			// create a set of sub rows for the header row so we can do compound columns
			// the first row is a special spacer row
			var columns = (this.subRows && this.subRows[0]) || this.columns,
				headerRows = [[]],
				contentColumns = [];
			// This first row is spacer row that will be made invisible (zero height)
			// with CSS, but it must be rendered as the first row since that is what
			// the table layout is driven by.
			headerRows[0].className = "dgrid-spacer-row";
			
			function processColumns(columns, level, hasLabel){
				var numColumns = 0,
					noop = function(){},
					column, children, hasChildLabels;
				
				function processColumn(column, i){
					children = column.children;
					hasChildLabels = column.children && (column.showChildHeaders !== false);
					if(children){
						// it has children, recursively process the children
						numColumns += (column.colSpan = processColumns(children, level + 1, hasChildLabels));
					}else{
						// it has no children, it is a normal header, add it to the content columns
						contentColumns.push(column);
						// add each one to the first spacer header row for proper layout of the header cells
						headerRows[0].push(lang.delegate(column, {renderHeaderCell: noop}));
						numColumns++;
					}
					if(!hasChildLabels){
						// create a header version of the column where we can define a specific rowSpan
						// we define the rowSpan as a negative, the number of levels less than the total number of rows, which we don't know yet
						column = lang.delegate(column, {rowSpan: -level});
					}
					// add the column to the header rows at the appropriate level
					if(hasLabel){
						(headerRows[level] || (headerRows[level] = [])).push(column);
					}
				}
				
				miscUtil.each(columns, processColumn, this);
				return numColumns;
			}
			processColumns(columns, 1, true);
			
			var numHeaderRows = headerRows.length,
				i, j, headerRow, headerColumn;
			// Now go back through and increase the rowSpans of the headers to be
			// total rows minus the number of levels they are at.
			for(i = 0; i < numHeaderRows; i++){
				headerRow = headerRows[i];
				for(j = 0; j < headerRow.length; j++){
					headerColumn = headerRow[j];
					if(headerColumn.rowSpan < 1){
						headerColumn.rowSpan += numHeaderRows;
					}
				}
			}
			// we need to set this to be used for subRows, so we make it a single row
			contentColumns = [contentColumns];
			// set our header rows so that the grid will use the alternate header row 
			// configuration for rendering the headers
			contentColumns.headerRows = headerRows;  
			this.subRows = contentColumns;
			this.inherited(arguments);
		}
	});
});
