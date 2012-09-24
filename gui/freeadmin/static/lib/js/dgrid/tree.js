define(["dojo/_base/declare", "dojo/_base/array", "dojo/_base/Deferred", "dojo/query", "dojo/on", "dojo/aspect", "./Grid", "dojo/has!touch?./util/touch", "put-selector/put"],
function(declare, arrayUtil, Deferred, querySelector, on, aspect, Grid, touchUtil, put){

return function(column){
	// summary:
	//		Adds tree navigation capability to a column.
	
	var originalRenderCell = column.renderCell || Grid.defaultRenderCell;
	
	var currentLevel, // tracks last rendered item level (for aspected insertRow)
		clicked; // tracks row that was clicked (for expand dblclick event handling)
	
	column.shouldExpand = column.shouldExpand || function(row, level, previouslyExpanded){
		// summary:
		//		Function called after each row is inserted to determine whether
		//		expand(rowElement, true) should be automatically called.
		//		The default implementation re-expands any rows that were expanded
		//		the last time they were rendered (if applicable).
		
		return previouslyExpanded;
	};
	
	aspect.after(column, "init", function(){
		var grid = column.grid,
			colSelector = ".dgrid-content .dgrid-column-" + column.id,
			transitionEventSupported,
			listeners = [], // to be removed when this column is "destroyed"
			tr, query;
		
		if(!grid.store){
			throw new Error("dgrid tree column plugin requires a store to operate.");
		}
		
		if (!column.renderExpando){
			// If no renderExpando function exists, create one with default logic.
			column.renderExpando = function(level, hasChildren, expanded){
				var dir = this.grid.isRTL ? "right" : "left",
					cls = ".dgrid-expando-icon",
					node;
				if(hasChildren){
					cls += ".ui-icon.ui-icon-triangle-1-" + (expanded ? "se" : "e");
				}
				node = put("div" + cls + "[style=margin-" + dir + ": " +
					(level * (this.indentWidth || 9)) + "px; float: " + dir + "]");
				node.innerHTML = "&nbsp;"; // for opera to space things properly
				return node;
			};
		}
		
		// Set up the event listener once and use event delegation for better memory use.
		listeners.push(grid.on(
			column.expandOn || ".dgrid-expando-icon:click," + colSelector + ":dblclick," + colSelector + ":keydown",
			function(event){
				var row = grid.row(event);	
				if((!grid.store.mayHaveChildren || grid.store.mayHaveChildren(row.data)) &&
						(event.type != "keydown" || event.keyCode == 32) &&
						!(event.type == "dblclick" && clicked && clicked.count > 1 &&
							row.id == clicked.id && event.target.className.indexOf("dgrid-expando-icon") > -1)){
					grid.expand(row);
				}
				
				// If the expando icon was clicked, update clicked object to prevent
				// potential over-triggering on dblclick (all tested browsers but IE < 9).
				if(event.target.className.indexOf("dgrid-expando-icon") > -1){
					if(clicked && clicked.id == grid.row(event).id){
						clicked.count++;
					}else{
						clicked = {
							id: grid.row(event).id,
							count: 1
						};
					}
				}
			})
		);
		
		if(touchUtil){
			// Also listen on double-taps of the cell.
			listeners.push(grid.on(touchUtil.selector(colSelector, touchUtil.dbltap),
				function(){ grid.expand(this); }));
		}
		
		// Set up hash to store IDs of expanded rows
		if(!grid._expanded){ grid._expanded = {}; }
		
		listeners.push(aspect.after(grid, "insertRow", function(rowElement){
			// Auto-expand (shouldExpand) considerations
			var row = this.row(rowElement),
				expanded = column.shouldExpand(row, currentLevel, this._expanded[row.id]);
			
			if(expanded){ this.expand(rowElement, true, true); }
			return rowElement; // pass return value through
		}));
		
		listeners.push(aspect.before(grid, "removeRow", function(rowElement, justCleanup){
			var connected = rowElement.connected;
			if(connected){
				// if it has a connected expando node, we process the children
				querySelector(">.dgrid-row", connected).forEach(function(element){
					grid.removeRow(element, true);
				});
				// now remove the connected container node
				if(!justCleanup){
					put(connected, "!");
				}
			}
		}));
		
		if(column.collapseOnRefresh){
			// Clear out the _expanded hash on each call to cleanup
			// (which generally coincides with refreshes, as well as destroy).
			listeners.push(aspect.after(grid, "cleanup", function(){
				this._expanded = {};
			}));
		}
		
		grid._calcRowHeight = function(rowElement){
			// we override this method so we can provide row height measurements that
			// include the children of a row
			var connected = rowElement.connected;
			// if connected, need to consider this in the total row height
			return rowElement.offsetHeight + (connected ? connected.offsetHeight : 0); 
		};
		
		grid.expand = function(target, expand, noTransition){
			// summary:
			//		Expands the row corresponding to the given target.
			// target: Object
			//		Row object (or something resolvable to one) to expand/collapse.
			// expand: Boolean?
			//		If specified, designates whether to expand or collapse the row;
			//		if unspecified, toggles the current state.
			
			var row = target.element ? target : grid.row(target);
			
			target = row.element;
			target = target.className.indexOf("dgrid-expando-icon") > -1 ? target :
				querySelector(".dgrid-expando-icon", target)[0];
			
			if(target && target.mayHaveChildren){
				// toggle or set expand/collapsed state based on optional 2nd argument
				var expanded = expand === undefined ? !this._expanded[row.id] : expand;
				
				// update the expando display
				target.className = "dgrid-expando-icon ui-icon ui-icon-triangle-1-" + (expanded ? "se" : "e");
				var preloadNode = target.preloadNode,
					rowElement = row.element,
					container, options;
				
				if(!preloadNode){
					// if the children have not been created, create a container, a preload node and do the 
					// query for the children
					container = rowElement.connected = put('div.dgrid-tree-container');//put(rowElement, '+...
					preloadNode = target.preloadNode = put(rowElement, '+', container, 'div.dgrid-preload');
					var query = function(options){
						return grid.store.getChildren(row.data, options);
					};
					query.level = target.level;
					if(column.allowDuplicates){
						// If allowDuplicates is specified, include parentId in options
						// in order to facilitate unique IDs for each occurrence of the
						// same item under multiple different parents.
						options = { parentId: row.id };
					}
					Deferred.when(
						grid.renderQuery ?
							grid._trackError(function(){
								return grid.renderQuery(query, preloadNode, options);
							}) :
							grid.renderArray(query(options), preloadNode, {query: query}),
						function(){
							// Expand once results are retrieved, if the row is still expanded.
							if(grid._expanded[row.id]){
								var scrollHeight = container.scrollHeight;
								container.style.height = scrollHeight ? scrollHeight + "px" : "auto";
							}
						}
					);
					var transitionend = function(event){
						// NOTE: this == container
						var height = this.style.height;
						if(height){
							// after expansion, ensure display is correct, and we set it to none for hidden containers to improve performance
							this.style.display = height == "0px" ? "none" : "block";
						}
						if(event){
							// now we need to reset the height to be auto, so future height changes 
							// (from children expansions, for example), will expand to the right height
							// However setting the height to auto or "" will cause an animation to zero height for some
							// reason, so we set the transition to be zero duration for the time being
							put(this, ".dgrid-tree-resetting");
							setTimeout(function(){
								// now we can turn off the zero duration transition after we have let it render
								put(container, "!dgrid-tree-resetting");
							});
							// this was triggered as a real event, we remember that so we don't fire the setTimeout's in the future
							transitionEventSupported = true;
						}else if(!transitionEventSupported){
							// if this was not triggered as a real event, we remember that so we shortcut animations
							transitionEventSupported = false;
						}
						// now set the height to auto
						this.style.height = "";
					};
					on(container, "transitionend,webkitTransitionEnd,oTransitionEnd,MSTransitionEnd", transitionend);
					if(!transitionEventSupported){
						setTimeout(function(){
							transitionend.call(container);
						}, 600);
					}
				}
				
				// Show or hide all the children.
				
				container = rowElement.connected;
				container.hidden = !expanded;
				var containerStyle = container.style,
					scrollHeight;
				
				// make sure it is visible so we can measure it
				if(transitionEventSupported === false || noTransition){
					containerStyle.display = expanded ? "block" : "none";
					containerStyle.height = "";
				}else{
					if(expanded){
						containerStyle.display = "block";
						scrollHeight = container.scrollHeight;
						containerStyle.height = "0px";
					}
					else{
						// if it will be hidden we need to be able to give a full height
						// without animating it, so it has the right starting point to animate to zero
						put(container, ".dgrid-tree-resetting");
						containerStyle.height = container.scrollHeight + "px";
					}
					// Perform a transition for the expand or collapse.
					setTimeout(function(){
						put(container, "!dgrid-tree-resetting");
						containerStyle.height =
							expanded ? (scrollHeight ? scrollHeight + "px" : "auto") : "0px";
					});
				}
				
				// Update _expanded map.
				if(expanded){
					this._expanded[row.id] = true;
				}else{
					delete this._expanded[row.id];
				}
			}
		}; // end function grid.expand
		
		// Set up a destroy function on column to tear down the listeners/aspects
		// established above if the grid's columns are redefined later.
		aspect.after(column, "destroy", function(){
			arrayUtil.forEach(listeners, function(l){ l.remove(); });
			// Delete methods we added/overrode on the instance.
			delete grid.expand;
			delete grid._calcRowHeight;
		});
	});
	
	column.renderCell = function(object, value, td, options){
		// summary:
		//		Renders a cell that can be expanded, creating more rows
		
		var grid = column.grid,
			level = Number(options && options.query && options.query.level) + 1,
			mayHaveChildren = !grid.store.mayHaveChildren || grid.store.mayHaveChildren(object),
			parentId = options.parentId,
			expando, node;
		
		level = currentLevel = isNaN(level) ? 0 : level;
		expando = column.renderExpando(level, mayHaveChildren,
			grid._expanded[(parentId ? parentId + "-" : "") + grid.store.getIdentity(object)]);
		expando.level = level;
		expando.mayHaveChildren = mayHaveChildren;
		
		node = originalRenderCell.call(column, object, value, td, options);
		if(node && node.nodeType){
			put(td, expando);
			put(td, node);
		}else{
			td.insertBefore(expando, td.firstChild);
		}
	};
	return column;
};
});