define(["dojo/_base/declare", "dojo/has", "dojo/on", "put-selector/put", "xstyle/css!../css/extensions/ColumnHider.css"],
function(declare, has, listen, put){
/*
 *	Column Hider plugin for dgrid
 *	Originally contributed by TRT 2011-09-28
 *
 *	A dGrid plugin that attaches a menu to a dgrid, along with a way of opening it,
 *	that will allow you to show and hide columns.  A few caveats:
 *
 *	1. Menu placement is entirely based on CSS definitions.
 *	2. If you want columns initially hidden, you must add "hidden: true" to your
 *		column definition.
 *	3. This implementation does NOT support ColumnSet, and has not been tested
 *		with multi-subrow records.
 *	4. Column show/hide is controlled via straight up HTML checkboxes.  If you 
 *		are looking for something more fancy, you'll probably need to use this
 *		definition as a template to write your own plugin.
 *
 */
	
	var activeGrid, // references grid for which the menu is currently open
		bodyListener, // references pausable event handler for body mousedown
		// Need to handle old IE specially for checkbox listener and for attribute.
		hasIE = has("ie"),
		hasIEQuirks = hasIE && has("quirks"),
		forAttr = hasIE < 8 || hasIEQuirks ? "htmlFor" : "for";
	
	function getColumnIdFromCheckbox(cb, grid){
		// Given one of the checkboxes from the hider menu,
		// return the id of the corresponding column.
		// (e.g. gridIDhere-hider-menu-check-colIDhere -> colIDhere)
		return cb.id.substr(grid.id.length + 18);
	}
	
	return declare(null, {
		// hiderMenuNode: DOMNode
		//		The node for the menu to show/hide columns.
		hiderMenuNode: null,
		
		// hiderToggleNode: DOMNode
		//		The node for the toggler to open the menu.
		hiderToggleNode: null,
		
		// _hiderMenuOpened: Boolean
		//		Records the current open/closed state of the menu.
		_hiderMenuOpened: false,
		
		// _columnHiderRules: Object
		//		Hash containing handles returned from styleColumn.
		_columnHiderRules: null,
		
		// _columnHiderCheckboxes: Object
		//		Hash containing checkboxes generated for menu items.
		_columnHiderCheckboxes: null,
		
		_renderHiderMenuEntries: function(){
			// summary:
			//		Iterates over subRows for the sake of adding items to the
			//		column hider menu.
			
			var subRows = this.subRows,
				srLength, cLength, sr, c;
			
			for(sr = 0, srLength = subRows.length; sr < srLength; sr++){
				for(c = 0, cLength = subRows[sr].length; c < cLength; c++){
					this._renderHiderMenuEntry(subRows[sr][c]);
				}
			}
		},
		
		_renderHiderMenuEntry: function(col){
			var id = col.id,
				div, checkId, checkbox;
			
			if(col.hidden){
				// Hidden state is true; hide the column.
				this._columnHiderRules[id] = this.styleColumn(id, "display: none");
			}
			
			// Allow cols to opt out of the hider (e.g. for selector column).
			if(col.unhidable){ return; }
			
			// Create the checkbox and label for each column selector.
			div = put("div.dgrid-hider-menu-row");
			checkId = this.domNode.id + "-hider-menu-check-" + id;
			
			this._columnHiderCheckboxes[id] = checkbox = put(div, "input#" + checkId +
					".dgrid-hider-menu-check.hider-menu-check-" + id + "[type=checkbox]");
			put(div, "label.dgrid-hider-menu-label.hider-menu-label" + id +
				"[" + forAttr + "=" + checkId + "]", col.label || col.field || "");
			
			put(this.hiderMenuNode, div);
			
			if(!col.hidden){
				// Hidden state is false; checkbox should be initially checked.
				// (Need to do this after adding to DOM to avoid IE6 clobbering it.)
				checkbox.checked = true;
			}
		},
		
		renderHeader: function(){
			var grid = this,
				hiderMenuNode = this.hiderMenuNode,
				hiderToggleNode = this.hiderToggleNode,
				id;
			
			this.inherited(arguments);
			
			if(!hiderMenuNode){ // first run
				// Assume that if this plugin is used, then columns are hidable.
				// Create the toggle node.
				hiderToggleNode = this.hiderToggleNode =
					put(this.headerScrollNode, "div.dgrid-hider-toggle.dgrid-cell-padding", "+");
				
				this._listeners.push(listen(hiderToggleNode, "click", function(e){
					grid._toggleColumnHiderMenu(e);
				}));
	
				// Create the column list, with checkboxes.
				hiderMenuNode = this.hiderMenuNode =
					put("div#dgrid-hider-menu-" + this.id + ".dgrid-hider-menu");
				
				// Make sure our menu is initially hidden, then attach to the document.
				hiderMenuNode.style.display = "none";
				put(this.domNode, hiderMenuNode);
				
				// Hook up delegated listener for modifications to checkboxes.
				this._listeners.push(listen(hiderMenuNode,
						".dgrid-hider-menu-check:" + (hasIE < 9 || hasIEQuirks ? "click" : "change"),
					function(e){
						grid._updateColumnHiddenState(
							getColumnIdFromCheckbox(e.target, grid), !e.target.checked);
					}
				));
				this._listeners.push(listen(hiderMenuNode, "mousedown", function(e){
					// Stop click events from propagating here, so that we can simply
					// track body clicks for hide without having to drill-up to check.
					e.stopPropagation();
				}));
				
				// Hook up top-level mousedown listener if it hasn't been yet.
				if(!bodyListener){
					bodyListener = listen.pausable(document, "mousedown", function(e){
						// If an event reaches this listener, the menu is open,
						// but a click occurred outside, so close the dropdown.
						activeGrid && activeGrid._toggleColumnHiderMenu(e);
					});
					bodyListener.pause(); // pause initially; will resume when menu opens
				}
			}else{ // subsequent run
				// Remove active rules, and clear out the menu (to be repopulated).
				for (id in this._columnHiderRules){
					this._columnHiderRules[id].remove();
				}
				hiderMenuNode.innerHTML = "";
			}
			
			this._columnHiderCheckboxes = {};
			this._columnHiderRules = {};

			// Populate menu with checkboxes/labels based on current columns.
			this._renderHiderMenuEntries();
		},
		
		isColumnHidden: function(id){
			// summary:
			//		Convenience method to determine current hidden state of a column
			return !!this._columnHiderRules[id];
		},
		
		_toggleColumnHiderMenu: function(){
			var hidden = this._hiderMenuOpened; // reflects hidden state after toggle
			// show or hide the hider menu
			this.hiderMenuNode.style.display = (hidden ? "none" : "");
			// pause or resume the listener for clicks outside the menu
			bodyListener[hidden ? "pause" : "resume"]();
			// update activeGrid appropriately
			activeGrid = hidden ? null : this;
			// toggle the instance property
			this._hiderMenuOpened = !hidden;
		},

		_updateColumnHiddenState: function(id, hidden){
			// summary:
			//		Performs internal work for toggleColumnHiddenState; see the public
			//		method for more information.
			
			if(!hidden){
				this._columnHiderRules[id].remove();
				delete this._columnHiderRules[id];
			}else{
				this._columnHiderRules[id] = this.styleColumn(id, "display: none;");
			}
			// emit event to notify of column state change
			listen.emit(this.domNode, "dgrid-columnstatechange", {
				column: this.columns[id],
				hidden: hidden
			});

			//	adjust the size of the header
			this.resize();
		},
		
		toggleColumnHiddenState: function(id, hidden){
			// summary:
			//		Shows or hides the column with the given id.
			// id: String
			//		ID of column to show/hide.
			// hide: Boolean?
			//		If specified, explicitly sets the hidden state of the specified
			//		column.  If unspecified, toggles the column from the current state.
			
			if(typeof hidden === "undefined"){ hidden = !this._columnHiderRules[id]; }
			this._updateColumnHiddenState(id, hidden);
			
			// Since this can be called directly, re-sync the appropriate checkbox.
			this._columnHiderCheckboxes[id].checked = !hidden;
		}
	});
});
