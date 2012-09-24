define(["dojo/_base/kernel", "dojo/_base/declare", "dojo/_base/Deferred", "dojo/on", "dojo/aspect", "dojo/query", "dojo/has", "put-selector/put", "xstyle/has-class", "./Grid", "dojo/_base/sniff", "xstyle/css!./css/columnset.css"],
function(kernel, declare, Deferred, listen, aspect, query, has, put, hasClass, Grid){
	var colsetidAttr = "data-dgrid-column-set-id";
	
	hasClass("safari", "ie-7");
	
	function positionScrollers(grid){
		var domNode = grid.domNode,
			scrollers = grid._columnSetScrollers,
			scrollerContents = grid._columnSetScrollerContents,
			columnSets = grid.columnSets,
			left = 0, scrollerWidth = 0,
			i, l, columnSetElement, contentWidth;
		for(i = 0, l = columnSets.length; i < l; i++){
			// iterate through the columnSets
			left += scrollerWidth;
			columnSetElement = query('.dgrid-column-set[' + colsetidAttr + '="' + i +'"]', domNode)[0];
			scrollerWidth = columnSetElement.offsetWidth;
			contentWidth = columnSetElement.firstChild.offsetWidth;
			scrollerContents[i].style.width = contentWidth + "px";
			scrollers[i].style.width = scrollerWidth + "px";
			scrollers[i].style.overflowX = contentWidth > scrollerWidth ? "scroll" : "auto"; // IE seems to need it be set explicitly
			scrollers[i].style.left = left + "px";
		}	
	}
	function adjustScrollLeft(grid, row){
		var scrollLefts = grid._columnSetScrollLefts;
		function doAdjustScrollLeft(){
			query(".dgrid-column-set", row).forEach(function(element){
				element.scrollLeft = scrollLefts[element.getAttribute(colsetidAttr)];
			});
		}
		if(has("ie") < 8 || has("quirks")){
			setTimeout(doAdjustScrollLeft, 1);
		}else{
			doAdjustScrollLeft();
		}
	}
	
	return declare([Grid], {
		// summary:
		//		Provides column sets to isolate horizontal scroll of sets of 
		//		columns from each other. This mainly serves the purpose of allowing for
		//		column locking.
		
		columnSets: [],
		createRowCells: function(tag, each){
			var row = put("table.dgrid-row-table");
			var tr = put(row, "tbody tr");
			for(var i = 0, l = this.columnSets.length; i < l; i++){
				// iterate through the columnSets
				var cell = put(tr, tag + ".dgrid-column-set-cell.dgrid-column-set-" + i +
					" div.dgrid-column-set[" + colsetidAttr + "=" + i + "]");
				cell.appendChild(this.inherited(arguments, [tag, each, this.columnSets[i]]));
			}
			return row;
		},
		renderArray: function(){
			var grid = this,
				rows = this.inherited(arguments);

			Deferred.when(rows, function(rows){
				for(var i = 0; i < rows.length; i++){
					adjustScrollLeft(grid, rows[i]);
				}
			});
			return rows;
		},
		renderHeader: function(){
			// summary:
			//		Setup the headers for the grid
			this.inherited(arguments);
			this.bodyNode.style.bottom = "17px";
			
			var columnSets = this.columnSets,
				domNode = this.domNode,
				scrollers = this._columnSetScrollers,
				scrollerContents = this._columnSetScrollerContents = {},
				scrollLefts = this._columnSetScrollLefts = {},
				grid = this,
				i, l;
			
			function onScroll(){
				var scrollLeft = this.scrollLeft;
				var colSetId = this.getAttribute(colsetidAttr);
				if(scrollLefts[colSetId] != scrollLeft){
					scrollLefts[colSetId] = scrollLeft;
					query('.dgrid-column-set[' + colsetidAttr + '="' + colSetId + '"],.dgrid-column-set-scroller[' + colsetidAttr + '="' + colSetId + '"]', domNode).
						forEach(function(element){
							element.scrollLeft = scrollLeft;
						});
				}
			}
			
			function putScroller(columnSet, i){
				// function called for each columnSet
				var scroller = scrollers[i] =
					put(domNode, "div.dgrid-column-set-scroller.dgrid-scrollbar-height.dgrid-column-set-scroller-" + i +
						"[" + colsetidAttr + "=" + i +"]");
				scrollerContents[i] = put(scroller, "div.dgrid-column-set-scroller-content");
				listen(scroller, "scroll", onScroll);
			}
			
			function reposition(){
				positionScrollers(grid);
			}
			
			if (scrollers) {
				// this isn't the first time; destroy existing scroller nodes first
				for(i in scrollers){
					put("!", scrollers[i]);
				}
			} else {
				// first-time-only operations: hook up event/aspected handlers
				aspect.after(this, "resize", reposition, true);
				aspect.after(this, "styleColumn", reposition, true);
				listen(domNode, ".dgrid-column-set:dgrid-cellfocusin", onScroll);
			}
			
			// reset to new object to be populated in loop below
			scrollers = this._columnSetScrollers = {};
			
			for(i = 0, l = columnSets.length; i < l; i++){
				putScroller(columnSets[i], i);
			}
			
			positionScrollers(this);
		},
		
		styleColumnSet: function(colsetId, css){
			// summary:
			//		Dynamically creates a stylesheet rule to alter a columnset's style.
			
			var rule = this.addCssRule("#" + this.domNode.id + " .dgrid-column-set-" + colsetId, css);
			positionScrollers(this);
			return rule;
		},
		
		_destroyColumns: function(){
			var columnSetsLength = this.columnSets.length,
				i, j, k, subRowsLength, len, columnSet, subRow, column;
			for(i = 0; i < columnSetsLength; i++){
				columnSet = this.columnSets[i];
				for(j = 0, subRowsLength = columnSet.length; j < subRowsLength; j++){
					subRow = columnSet[j];
					for(k = 0, len = subRow.length; k < len; k++){
						column = subRow[k];
						if(typeof column.destroy === "function"){ column.destroy(); }
					}
				}
			}
		},
		configStructure: function(){
			this.columns = {};
			for(var i = 0, l = this.columnSets.length; i < l; i++){
				// iterate through the columnSets
				var columnSet = this.columnSets[i];
				for(var j = 0; j < columnSet.length; j++){
					columnSet[j] = this._configColumns(i + '-' + j + '-', columnSet[j]);
				}
			}
		},
		_setColumnSets: function(columnSets){
			this._destroyColumns();
			this.columnSets = columnSets;
			this._updateColumns();
		},
		setColumnSets: function(columnSets){
			kernel.deprecated("setColumnSets(...)", 'use set("columnSets", ...) instead', "dgrid 1.0");
			this.set("columnSets", columnSets);
		}
	});
});
