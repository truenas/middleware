define(["./Grid", "dojo/_base/declare", "put-selector/put"],
function(Grid, declare, put){
	// summary:
	//		This module supports parsing grid structure information from an HTML table.
	//		This module does NOT support ColumnSets; see GridWithColumnSetsFromHtml
	
	// name of data attribute to check for column properties
	var bagName = "data-dgrid-column";
	
	function getSubRowsFromDom(domNode){
		// summary:
		//		generate columns from DOM. Should this be in here, or a separate module?
		var
			columns = [], // to be pushed upon / returned
			trs = domNode.getElementsByTagName("tr"),
			trslen = trs.length,
			getCol = GridFromHtml.utils.getColumnFromCell,
			rowColumns, tr, ths, thslen;
		
		for(var i = 0; i < trslen; i++){
			rowColumns = [];
			columns.push(rowColumns);
			tr = trs[i];
			ths = tr.getElementsByTagName("th"), thslen = ths.length;
			for(var j = 0; j < thslen; j++){
				rowColumns.push(getCol(ths[j]));
			}
		}
		if(tr){
			// NOTE: this assumes that applicable TRs were ONLY found under one
			// grouping element (e.g. thead)
			domNode.removeChild(tr.parentNode);
		}
		
		return columns;
	}
	
	var GridFromHtml = declare(Grid, {
		configStructure: function(){
			// summary:
			//		Configure subRows based on HTML originally in srcNodeRef
			if(!this._checkedTrs){
				this._checkedTrs = true;
				this.subRows = getSubRowsFromDom(this.srcNodeRef, this.subRows);
			}
			return this.inherited(arguments);
		},
		
		create: function(params, srcNodeRef){
			// We need to replace srcNodeRef, presumably a table, with a div.
			// (Otherwise we'll generate highly invalid markup, which IE doesn't like)
			var
				div = document.createElement("div"),
				id = srcNodeRef.id,
				style = srcNodeRef.getAttribute("style");
			
			// Copy some commonly-used attributes...
			if(id){ this.id = id; } // will be propagated in List's create
			div.className = srcNodeRef.className;
			style && div.setAttribute("style", style);
			
			// replace srcNodeRef in DOM with the div
			srcNodeRef.parentNode.replaceChild(div, srcNodeRef);
			
			(params = params || {}).srcNodeRef = srcNodeRef;
			// call inherited with the new node
			// (but configStructure will look at srcNodeRef)
			this.inherited(arguments, [params, div]);
			
			// destroy srcNodeRef for good now that we're done with it
			put(srcNodeRef, "!");
		}
	});
	
	// hang some utility functions, potentially useful for extensions
	GridFromHtml.utils = {
		// Functions for getting various types of values from HTML attributes
		getBoolFromAttr: function(node, attr){
			// used for e.g. sortable
			var val = node.getAttribute(attr);
			return val && val !== "false";
		},
		getNumFromAttr: function(node, attr){
			// used for e.g. rowSpan, colSpan
			var val = node.getAttribute(attr);
			val = val && Number(val);
			return isNaN(val) ? undefined : val;
		},
		getPropsFromNode: function(node){
			// used to pull properties out of bag e.g. "data-dgrid-column".
			var obj, str = node.getAttribute(bagName);
			if(!str){ return {}; } // no props bag specified!
			
			// Yes, eval is evil, but this is ultimately the same thing that
			// dojo.parser does for objects.
			try{
				obj = eval("(" + str + ")");
			}catch(e){
				throw new Error("Error in " + bagName + " {" + str + "}: " + e.toString());
			}
			return obj;
		},
		
		// Function for aggregating th attributes into column properties
		getColumnFromCell: function(th){
			var
				getNum = GridFromHtml.utils.getNumFromAttr,
				obj, tmp;
			
			// Look for properties in data attribute.
			// It's imperative that we hold on to this object as returned, as the
			// object may be augmented further by other sources,
			// e.g. Grid adding the grid property to reference the instance.
			obj = GridFromHtml.utils.getPropsFromNode(th);
			
			// inspect standard attributes, but data attribute takes precedence
			obj.label = obj.label || th.innerHTML;
			obj.field = obj.field || th.className || th.innerHTML;
			if(!obj.className && th.className){ obj.className = th.className; }
			if(!obj.rowSpan && (tmp = getNum(th, "rowspan"))){ obj.rowSpan = tmp; }
			if(!obj.colSpan && (tmp = getNum(th, "colspan"))){ obj.colSpan = tmp; }
			
			return obj;
		}
	};
	return GridFromHtml;
});