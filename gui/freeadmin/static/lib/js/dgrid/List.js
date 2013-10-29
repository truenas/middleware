define(["dojo/_base/kernel", "dojo/_base/declare", "dojo/on", "dojo/has", "./util/misc", "dojo/has!touch?./TouchScroll", "xstyle/has-class", "put-selector/put", "dojo/_base/sniff", "xstyle/css!./css/dgrid.css"], 
function(kernel, declare, listen, has, miscUtil, TouchScroll, hasClass, put){
	// Add user agent/feature CSS classes 
	hasClass("mozilla", "opera", "webkit", "ie", "ie-6", "ie-6-7", "quirks", "no-quirks", "touch");
	
	var oddClass = "dgrid-row-odd",
		evenClass = "dgrid-row-even",
		scrollbarWidth, scrollbarHeight;
	
	function byId(id){
		return document.getElementById(id);
	}
	
	function getScrollbarSize(node, dimension){
		// Used by has tests for scrollbar width/height
		var body = document.body,
			size;
		
		put(body, node, ".dgrid-scrollbar-measure");
		size = node["offset" + dimension] - node["client" + dimension];
		
		put(node, "!dgrid-scrollbar-measure");
		body.removeChild(node);
		
		return size;
	}
	has.add("dom-scrollbar-width", function(global, doc, element){
		return getScrollbarSize(element, "Width");
	});
	has.add("dom-scrollbar-height", function(global, doc, element){
		return getScrollbarSize(element, "Height");
	});
	
	// var and function for autogenerating ID when one isn't provided
	var autogen = 0;
	function generateId(){
		return "dgrid_" + autogen++;
	}
	
	// common functions for class and className setters/getters
	// (these are run in instance context)
	var spaceRx = / +/g;
	function setClass(cls){
		// Format input appropriately for use with put...
		var putClass = cls ? "." + cls.replace(spaceRx, ".") : "";
		
		// Remove any old classes, and add new ones.
		if(this._class){
			putClass = "!" + this._class.replace(spaceRx, "!") + putClass;
		}
		put(this.domNode, putClass);
		
		// Store for later retrieval/removal.
		this._class = cls;
	}
	function getClass(){
		return this._class;
	}
	
	// window resize event handler, run in context of List instance
	var winResizeHandler = has("ie") < 7 && !has("quirks") ? function(){
		// IE6 triggers window.resize on any element resize;
		// avoid useless calls (and infinite loop if height: auto).
		// The measurement logic here is based on dojo/window logic.
		var root, w, h, dims;
		
		if(!this._started){ return; } // no sense calling resize yet
		
		root = document.documentElement;
		w = root.clientWidth;
		h = root.clientHeight;
		dims = this._prevWinDims || [];
		if(dims[0] !== w || dims[1] !== h){
			this.resize();
			this._prevWinDims = [w, h];
		}
	} :
	function(){
		if(this._started){ this.resize(); }
	};
	
	// Desktop versions of functions, deferred to when there is no touch support,
	// or when the useTouchScroll instance property is set to false
	
	function desktopGetScrollPosition(){
		return {
			x: this.bodyNode.scrollLeft,
			y: this.bodyNode.scrollTop
		};
	}
	
	function desktopScrollTo(options){
		if(typeof options.x !== "undefined"){
			this.bodyNode.scrollLeft = options.x;
		}
		if(typeof options.y !== "undefined"){
			this.bodyNode.scrollTop = options.y;
		}
	}
	
	return declare(has("touch") ? TouchScroll : null, {
		tabableHeader: false,
		// showHeader: Boolean
		//		Whether to render header (sub)rows.
		showHeader: false,
		
		// showFooter: Boolean
		//		Whether to render footer area.  Extensions which display content
		//		in the footer area should set this to true.
		showFooter: false,
		
		// maintainOddEven: Boolean
		//		Whether to maintain the odd/even classes when new rows are inserted.
		//		This can be disabled to improve insertion performance if odd/even styling is not employed.
		maintainOddEven: true,
		
		// cleanAddedRules: Boolean
		//		Whether to track rules added via the addCssRule method to be removed
		//		when the list is destroyed.  Note this is effective at the time of
		//		the call to addCssRule, not at the time of destruction.
		cleanAddedRules: true,
		
		// useTouchScroll: Boolean
		//		If touch support is available, this determines whether to
		//		incorporate logic from the TouchScroll module (at the expense of
		//		normal desktop/mouse or native mobile scrolling functionality).
		useTouchScroll: true,

		// cleanEmptyObservers: Boolean
		//		Whether to clean up observers for empty result sets.
		cleanEmptyObservers: true,

		// highlightDuration: Integer
		//		The amount of time (in milliseconds) that a row should remain
		//		highlighted after it has been updated.
		highlightDuration: 250,
		
		postscript: function(params, srcNodeRef){
			// perform setup and invoke create in postScript to allow descendants to
			// perform logic before create/postCreate happen (a la dijit/_WidgetBase)
			var grid = this;
			
			(this._Row = function(id, object, element){
				this.id = id;
				this.data = object;
				this.element = element;
			}).prototype.remove = function(){
				grid.removeRow(this.element);
			};
			
			if(srcNodeRef){
				// normalize srcNodeRef and store on instance during create process.
				// Doing this in postscript is a bit earlier than dijit would do it,
				// but allows subclasses to access it pre-normalized during create.
				this.srcNodeRef = srcNodeRef =
					srcNodeRef.nodeType ? srcNodeRef : byId(srcNodeRef);
			}
			this.create(params, srcNodeRef);
		},
		listType: "list",
		
		create: function(params, srcNodeRef){
			var domNode = this.domNode = srcNodeRef || put("div"),
				cls;
			
			if(params){
				this.params = params;
				declare.safeMixin(this, params);
				
				// Check for initial class or className in params or on domNode
				cls = params["class"] || params.className || domNode.className;
				
				// handle sort param - TODO: revise @ 0.4 when _sort -> sort
				this._sort = params.sort || [];
				delete this.sort; // ensure back-compat method isn't shadowed
			}else{
				this._sort = [];
			}
			
			// ensure arrays and hashes are initialized
			this.observers = [];
			this._numObservers = 0;
			this._listeners = [];
			this._rowIdToObject = {};
			
			this.postMixInProperties && this.postMixInProperties();
			
			// Apply id to widget and domNode,
			// from incoming node, widget params, or autogenerated.
			this.id = domNode.id = domNode.id || this.id || generateId();
			
			// Perform initial rendering, and apply classes if any were specified.
			this.buildRendering();
			if(cls){ setClass.call(this, cls); }
			
			this.postCreate();
			
			// remove srcNodeRef instance property post-create
			delete this.srcNodeRef;
			// to preserve "it just works" behavior, call startup if we're visible
			if(this.domNode.offsetHeight){
				this.startup();
			}
		},
		buildRendering: function(){
			var domNode = this.domNode,
				self = this,
				headerNode, spacerNode, bodyNode, footerNode, isRTL;
			
			// Detect RTL on html/body nodes; taken from dojo/dom-geometry
			isRTL = this.isRTL = (document.body.dir || document.documentElement.dir ||
				document.body.style.direction).toLowerCase() == "rtl";
			
			// Clear out className (any pre-applied classes will be re-applied via the
			// class / className setter), then apply standard classes/attributes
			domNode.className = "";
			
			put(domNode, "[role=grid].ui-widget.dgrid.dgrid-" + this.listType);
			
			// Place header node (initially hidden if showHeader is false).
			headerNode = this.headerNode = put(domNode, 
				"div.dgrid-header.dgrid-header-row.ui-widget-header" +
				(this.showHeader ? "" : ".dgrid-header-hidden"));
			if(has("quirks") || has("ie") < 8){
				spacerNode = put(domNode, "div.dgrid-spacer");
			}
			bodyNode = this.bodyNode = put(domNode, "div.dgrid-scroller");
			
			// firefox 4 until at least 10 adds overflow: auto elements to the tab index by default for some
			// reason; force them to be not tabbable
			bodyNode.tabIndex = -1;
			
			this.headerScrollNode = put(domNode, "div.dgrid-header-scroll.dgrid-scrollbar-width.ui-widget-header");
			
			// Place footer node (initially hidden if showFooter is false).
			footerNode = this.footerNode = put("div.dgrid-footer" +
				(this.showFooter ? "" : ".dgrid-footer-hidden"));
			put(domNode, footerNode);
			
			if(isRTL){
				domNode.className += " dgrid-rtl" + (has("webkit") ? "" : " dgrid-rtl-nonwebkit");
			}
			
			listen(bodyNode, "scroll", function(event){
				if(self.showHeader){
					// keep the header aligned with the body
					headerNode.scrollLeft = event.scrollLeft || bodyNode.scrollLeft;
				}
				// re-fire, since browsers are not consistent about propagation here
				event.stopPropagation();
				listen.emit(domNode, "scroll", {scrollTarget: bodyNode});
			});
			this.configStructure();
			this.renderHeader();
			
			this.contentNode = this.touchNode = put(this.bodyNode, "div.dgrid-content.ui-widget-content");
			// add window resize handler, with reference for later removal if needed
			this._listeners.push(this._resizeHandle = listen(window, "resize",
				miscUtil.throttleDelayed(winResizeHandler, this)));
		},
		
		postCreate: has("touch") ? function(){
			if(this.useTouchScroll){
				this.inherited(arguments);
			}
		} : function(){},
		
		startup: function(){
			// summary:
			//		Called automatically after postCreate if the component is already
			//		visible; otherwise, should be called manually once placed.
			
			if(this._started){ return; } // prevent double-triggering
			this.inherited(arguments);
			this._started = true;
			this.resize();
			// apply sort (and refresh) now that we're ready to render
			this.set("sort", this._sort);
		},
		
		configStructure: function(){
			// does nothing in List, this is more of a hook for the Grid
		},
		resize: function(){
			var
				bodyNode = this.bodyNode,
				headerNode = this.headerNode,
				footerNode = this.footerNode,
				headerHeight = headerNode.offsetHeight,
				footerHeight = this.showFooter ? footerNode.offsetHeight : 0,
				quirks = has("quirks") || has("ie") < 7;
			
			this.headerScrollNode.style.height = bodyNode.style.marginTop = headerHeight + "px";
			bodyNode.style.marginBottom = footerHeight + "px";
			
			if(quirks){
				// in IE6 and quirks mode, the "bottom" CSS property is ignored.
				// We guard against negative values in case of issues with external CSS.
				bodyNode.style.height = ""; // reset first
				bodyNode.style.height =
					Math.max((this.domNode.offsetHeight - headerHeight - footerHeight), 0) + "px";
				if (footerHeight) {
					// Work around additional glitch where IE 6 / quirks fails to update
					// the position of the bottom-aligned footer; this jogs its memory.
					footerNode.style.bottom = '1px';
					setTimeout(function(){ footerNode.style.bottom = ''; }, 0);
				}
			}
			
			if(!scrollbarWidth){
				// Measure the browser's scrollbar width using a DIV we'll delete right away
				scrollbarWidth = has("dom-scrollbar-width");
				scrollbarHeight = has("dom-scrollbar-height");
				
				// Avoid issues with certain widgets inside in IE7, and
				// ColumnSet scroll issues with all supported IE versions
				if(has("ie")){
					scrollbarWidth++;
					scrollbarHeight++;
				}
				
				// add rules that can be used where scrollbar width/height is needed
				miscUtil.addCssRule(".dgrid-scrollbar-width", "width: " + scrollbarWidth + "px");
				miscUtil.addCssRule(".dgrid-scrollbar-height", "height: " + scrollbarHeight + "px");
				
				if(scrollbarWidth != 17 && !quirks){
					// for modern browsers, we can perform a one-time operation which adds
					// a rule to account for scrollbar width in all grid headers.
					miscUtil.addCssRule(".dgrid-header", "right: " + scrollbarWidth + "px");
					// add another for RTL grids
					miscUtil.addCssRule(".dgrid-rtl-nonwebkit .dgrid-header", "left: " + scrollbarWidth + "px");
				}
			}
			
			if(quirks){
				// old IE doesn't support left + right + width:auto; set width directly
				headerNode.style.width = bodyNode.clientWidth + "px";
				setTimeout(function(){
					// sync up (after the browser catches up with the new width)
					headerNode.scrollLeft = bodyNode.scrollLeft;
				}, 0);
			}
		},
		
		addCssRule: function(selector, css){
			// summary:
			//		Version of util/misc.addCssRule which tracks added rules and removes
			//		them when the List is destroyed.
			
			var rule = miscUtil.addCssRule(selector, css);
			if(this.cleanAddedRules){
				// Although this isn't a listener, it shares the same remove contract
				this._listeners.push(rule);
			}
			return rule;
		},
		
		on: function(eventType, listener){
			// delegate events to the domNode
			var signal = listen(this.domNode, eventType, listener);
			if(!has("dom-addeventlistener")){
				this._listeners.push(signal);
			}
			return signal;
		},
		
		cleanup: function(){
			// summary:
			//		Clears out all rows currently in the list.
			
			var observers = this.observers,
				i;
			for(i in this._rowIdToObject){
				if(this._rowIdToObject[i] != this.columns){
					var rowElement = byId(i);
					if(rowElement){
						this.removeRow(rowElement, true);
					}
				}
			}
			// remove any store observers
			for(i = 0;i < observers.length; i++){
				var observer = observers[i];
				observer && observer.cancel();
			}
			this.observers = [];
			this._numObservers = 0;
			this.preload = null;
		},
		destroy: function(){
			// summary:
			//		Destroys this grid
			
			// Remove any event listeners and other such removables
			if(this._listeners){ // Guard against accidental subsequent calls to destroy
				for(var i = this._listeners.length; i--;){
					this._listeners[i].remove();
				}
				delete this._listeners;
			}
			
			this.cleanup();
			// destroy DOM
			put(this.domNode, "!");
			this.inherited(arguments);
		},
		refresh: function(){
			// summary:
			//		refreshes the contents of the grid
			this.cleanup();
			this._rowIdToObject = {};
			this._autoId = 0;
			
			// make sure all the content has been removed so it can be recreated
			this.contentNode.innerHTML = "";
			// Ensure scroll position always resets (especially for TouchScroll).
			this.scrollTo({ x: 0, y: 0 });
		},
		
		newRow: function(object, parentNode, beforeNode, i, options){
			if(parentNode){
				var row = this.insertRow(object, parentNode, beforeNode, i, options);
				put(row, ".ui-state-highlight");
				setTimeout(function(){
					put(row, "!ui-state-highlight");
				}, this.highlightDuration);
				return row;
			}
		},
		adjustRowIndices: function(firstRow){
			// this traverses through rows to maintain odd/even classes on the rows when indexes shift;
			var next = firstRow;
			var rowIndex = next.rowIndex;
			if(rowIndex > -1){ // make sure we have a real number in case this is called on a non-row
				do{
					// Skip non-numeric, non-rows
					if(next.rowIndex > -1){
						if(this.maintainOddEven){
							if((next.className + ' ').indexOf("dgrid-row ") > -1){
								put(next, '.' + (rowIndex % 2 == 1 ? oddClass : evenClass) + '!' + (rowIndex % 2 == 0 ? oddClass : evenClass));
							}
						}
						next.rowIndex = rowIndex++;
					}
				}while((next = next.nextSibling) && next.rowIndex != rowIndex);
			}
		},
		renderArray: function(results, beforeNode, options){
			// summary:
			//		This renders an array or collection of objects as rows in the grid, before the
			//		given node. This will listen for changes in the collection if an observe method
			//		is available (as it should be if it comes from an Observable data store).
			options = options || {};
			var self = this,
				start = options.start || 0,
				observers = this.observers,
				rows, container, observerIndex;
			
			if(!beforeNode){
				this._lastCollection = results;
			}
			if(results.observe){
				// observe the results for changes
				self._numObservers++;
				observerIndex = observers.push(results.observe(function(object, from, to){
					var row, firstRow, nextNode, parentNode;
					
					function advanceNext() {
						nextNode = (nextNode.connected || nextNode).nextSibling;
					}
					
					// a change in the data took place
					if(from > -1 && rows[from]){
						// remove from old slot
						row = rows.splice(from, 1)[0];
						// check to make the sure the node is still there before we try to remove it, (in case it was moved to a different place in the DOM)
						if(row.parentNode == container){
							firstRow = row.nextSibling;
							if(firstRow){ // it's possible for this to have been already removed if it is in overlapping query results
								if(from != to){ // if from and to are identical, it is an in-place update and we don't want to alter the rowIndex at all
									firstRow.rowIndex--; // adjust the rowIndex so adjustRowIndices has the right starting point
								}
							}
							self.removeRow(row); // now remove
						}
						// the removal of rows could cause us to need to page in more items
						if(self._processScroll){
							self._processScroll();
						}
					}
					if(to > -1){
						// Add to new slot (either before an existing row, or at the end)
						// First determine the DOM node that this should be placed before.
						if(rows.length){
							nextNode = rows[to];
							if(!nextNode){
								nextNode = rows[to - 1];
								if(nextNode){
									// Make sure to skip connected nodes, so we don't accidentally
									// insert a row in between a parent and its children.
									advanceNext();
								}
							}
						}else{
							// There are no rows.  Allow for subclasses to insert new rows somewhere other than
							// at the end of the parent node.
							nextNode = self._getFirstRowSibling && self._getFirstRowSibling(container);
						}
						// Make sure we don't trip over a stale reference to a
						// node that was removed, or try to place a node before
						// itself (due to overlapped queries)
						if(row && nextNode && row.id === nextNode.id){
							advanceNext();
						}
						if(nextNode && !nextNode.parentNode){
							nextNode = byId(nextNode.id);
						}
						parentNode = (beforeNode && beforeNode.parentNode) ||
							(nextNode && nextNode.parentNode) || self.contentNode;
						row = self.newRow(object, parentNode, nextNode, options.start + to, options);
						
						if(row){
							row.observerIndex = observerIndex;
							rows.splice(to, 0, row);
							if(!firstRow || to < from){
								// the inserted row is first, so we update firstRow to point to it
								var previous = row.previousSibling;
								// if we are not in sync with the previous row, roll the firstRow back one so adjustRowIndices can sync everything back up.
								firstRow = !previous || previous.rowIndex + 1 == row.rowIndex || row.rowIndex == 0 ?
									row : previous;
							}
						}
						options.count++;
					}
					from != to && firstRow && self.adjustRowIndices(firstRow);
					self._onNotification(rows, object, from, to);
				}, true)) - 1;
			}
			var rowsFragment = document.createDocumentFragment(),
				lastRow;
			
			function mapEach(object){
				lastRow = self.insertRow(object, rowsFragment, null, start++, options);
				lastRow.observerIndex = observerIndex;
				return lastRow;
			}
			function whenError(error){
				if(typeof observerIndex !== "undefined"){
					observers[observerIndex].cancel();
					observers[observerIndex] = 0;
					self._numObservers--;
				}
				if(error){
					throw error;
				}
			}
			function whenDone(resolvedRows){
				container = beforeNode ? beforeNode.parentNode : self.contentNode;
				if(container && container.parentNode &&
						(container !== self.contentNode || resolvedRows.length)){
					container.insertBefore(rowsFragment, beforeNode || null);
					lastRow = resolvedRows[resolvedRows.length - 1];
					lastRow && self.adjustRowIndices(lastRow);
				}else if(observers[observerIndex] && self.cleanEmptyObservers){
					// Remove the observer and don't bother inserting;
					// rows are already out of view or there were none to track
					whenError();
				}
				return (rows = resolvedRows);
			}
			
			// now render the results
			if(results.map){
				rows = results.map(mapEach, console.error);
				if(rows.then){
					return rows.then(whenDone, whenError);
				}
			}else{
				rows = [];
				for(var i = 0, l = results.length; i < l; i++){
					rows[i] = mapEach(results[i]);
				}
			}
			
			return whenDone(rows);
		},

		_onNotification: function(rows, object, from, to){
			// summary:
			//		Protected method called whenever a store notification is observed.
			//		Intended to be extended as necessary by mixins/extensions.
		},

		renderHeader: function(){
			// no-op in a plain list
		},
		
		_autoId: 0,
		insertRow: function(object, parent, beforeNode, i, options){
			// summary:
			//		Creates a single row in the grid.
			
			// Include parentId within row identifier if one was specified in options.
			// (This is used by tree to allow the same object to appear under
			// multiple parents.)
			var parentId = options.parentId,
				id = this.id + "-row-" + (parentId ? parentId + "-" : "") + 
					((this.store && this.store.getIdentity) ? 
						this.store.getIdentity(object) : this._autoId++),
				row = byId(id),
				previousRow = row && row.previousSibling;
			
			if(row){// if it existed elsewhere in the DOM, we will remove it, so we can recreate it
				this.removeRow(row);
			}
			row = this.renderRow(object, options);
			row.className = (row.className || "") + " ui-state-default dgrid-row " + (i % 2 == 1 ? oddClass : evenClass);
			// get the row id for easy retrieval
			this._rowIdToObject[row.id = id] = object;
			parent.insertBefore(row, beforeNode || null);
			if(previousRow){
				// in this case, we are pulling the row from another location in the grid, and we need to readjust the rowIndices from the point it was removed
				this.adjustRowIndices(previousRow);
			}
			row.rowIndex = i;
			return row;
		},
		renderRow: function(value, options){
			// summary:
			//		Responsible for returning the DOM for a single row in the grid.
			
			return put("div", "" + value);
		},
		removeRow: function(rowElement, justCleanup){
			// summary:
			//		Simply deletes the node in a plain List.
			//		Column plugins may aspect this to implement their own cleanup routines.
			// rowElement: Object|DOMNode
			//		Object or element representing the row to be removed.
			// justCleanup: Boolean
			//		If true, the row element will not be removed from the DOM; this can
			//		be used by extensions/plugins in cases where the DOM will be
			//		massively cleaned up at a later point in time.
			
			rowElement = rowElement.element || rowElement;
			delete this._rowIdToObject[rowElement.id];
			if(!justCleanup){
				put(rowElement, "!");
			}
		},
		
		row: function(target){
			// summary:
			//		Get the row object by id, object, node, or event
			var id;
			
			if(target instanceof this._Row){ return target; } // no-op; already a row
			
			if(target.target && target.target.nodeType){
				// event
				target = target.target;
			}
			if(target.nodeType){
				var object;
				do{
					var rowId = target.id;
					if((object = this._rowIdToObject[rowId])){
						return new this._Row(rowId.substring(this.id.length + 5), object, target); 
					}
					target = target.parentNode;
				}while(target && target != this.domNode);
				return;
			}
			if(typeof target == "object"){
				// assume target represents a store item
				id = this.store.getIdentity(target);
			}else{
				// assume target is a row ID
				id = target;
				target = this._rowIdToObject[this.id + "-row-" + id];
			}
			return new this._Row(id, target, byId(this.id + "-row-" + id));
		},
		cell: function(target){
			// this doesn't do much in a plain list
			return {
				row: this.row(target)
			};
		},
		
		_move: function(item, steps, targetClass, visible){
			var nextSibling, current, element;
			// Start at the element indicated by the provided row or cell object.
			element = current = item.element;
			steps = steps || 1;
			
			do{
				// Outer loop: move in the appropriate direction.
				if((nextSibling = current[steps < 0 ? "previousSibling" : "nextSibling"])){
					do{
						// Inner loop: advance, and dig into children if applicable.
						current = nextSibling;
						if(current && (current.className + " ").indexOf(targetClass + " ") > -1){
							// Element with the appropriate class name; count step, stop digging.
							element = current;
							steps += steps < 0 ? 1 : -1;
							break;
						}
						// If the next sibling isn't a match, drill down to search, unless
						// visible is true and children are hidden.
					}while((nextSibling = (!visible || !current.hidden) && current[steps < 0 ? "lastChild" : "firstChild"]));
				}else{
					current = current.parentNode;
					if(current === this.bodyNode || current === this.headerNode){
						// Break out if we step out of the navigation area entirely.
						break;
					}
				}
			}while(steps);
			// Return the final element we arrived at, which might still be the
			// starting element if we couldn't navigate further in that direction.
			return element;
		},
		
		up: function(row, steps, visible){
			// summary:
			//		Returns the row that is the given number of steps (1 by default)
			//		above the row represented by the given object.
			// row:
			//		The row to navigate upward from.
			// steps:
			//		Number of steps to navigate up from the given row; default is 1.
			// visible:
			//		If true, rows that are currently hidden (i.e. children of
			//		collapsed tree rows) will not be counted in the traversal.
			// returns:
			//		A row object representing the appropriate row.  If the top of the
			//		list is reached before the given number of steps, the first row will
			//		be returned.
			if(!row.element){ row = this.row(row); }
			return this.row(this._move(row, -(steps || 1), "dgrid-row", visible));
		},
		down: function(row, steps, visible){
			// summary:
			//		Returns the row that is the given number of steps (1 by default)
			//		below the row represented by the given object.
			// row:
			//		The row to navigate downward from.
			// steps:
			//		Number of steps to navigate down from the given row; default is 1.
			// visible:
			//		If true, rows that are currently hidden (i.e. children of
			//		collapsed tree rows) will not be counted in the traversal.
			// returns:
			//		A row object representing the appropriate row.  If the bottom of the
			//		list is reached before the given number of steps, the last row will
			//		be returned.
			if(!row.element){ row = this.row(row); }
			return this.row(this._move(row, steps || 1, "dgrid-row", visible));
		},
		
		scrollTo: has("touch") ? function(options){
			// If TouchScroll is the superclass, defer to its implementation.
			return this.useTouchScroll ? this.inherited(arguments) :
				desktopScrollTo.call(this, options);
		} : desktopScrollTo,
		
		getScrollPosition: has("touch") ? function(){
			// If TouchScroll is the superclass, defer to its implementation.
			return this.useTouchScroll ? this.inherited(arguments) :
				desktopGetScrollPosition.call(this);
		} : desktopGetScrollPosition,
		
		get: function(/*String*/ name /*, ... */){
			// summary:
			//		Get a property on a List instance.
			//	name:
			//		The property to get.
			//	returns:
			//		The property value on this List instance.
			// description:
			//		Get a named property on a List object. The property may
			//		potentially be retrieved via a getter method in subclasses. In the base class
			//		this just retrieves the object's property.
			
			var fn = "_get" + name.charAt(0).toUpperCase() + name.slice(1);
			
			if(typeof this[fn] === "function"){
				return this[fn].apply(this, [].slice.call(arguments, 1));
			}
			
			// Alert users that try to use Dijit-style getter/setters so they don’t get confused
			// if they try to use them and it does not work
			if(!has("dojo-built") && typeof this[fn + "Attr"] === "function"){
				console.warn("dgrid: Use " + fn + " instead of " + fn + "Attr for getting " + name);
			}
			
			return this[name];
		},
		
		set: function(/*String*/ name, /*Object*/ value /*, ... */){
			//	summary:
			//		Set a property on a List instance
			//	name:
			//		The property to set.
			//	value:
			//		The value to set in the property.
			//	returns:
			//		The function returns this List instance.
			//	description:
			//		Sets named properties on a List object.
			//		A programmatic setter may be defined in subclasses.
			//
			//		set() may also be called with a hash of name/value pairs, ex:
			//	|	myObj.set({
			//	|		foo: "Howdy",
			//	|		bar: 3
			//	|	})
			//		This is equivalent to calling set(foo, "Howdy") and set(bar, 3)
			
			if(typeof name === "object"){
				for(var k in name){
					this.set(k, name[k]);
				}
			}else{
				var fn = "_set" + name.charAt(0).toUpperCase() + name.slice(1);
				
				if(typeof this[fn] === "function"){
					this[fn].apply(this, [].slice.call(arguments, 1));
				}else{
					// Alert users that try to use Dijit-style getter/setters so they don’t get confused
					// if they try to use them and it does not work
					if(!has("dojo-built") && typeof this[fn + "Attr"] === "function"){
						console.warn("dgrid: Use " + fn + " instead of " + fn + "Attr for setting " + name);
					}
					
					this[name] = value;
				}
			}
			
			return this;
		},
		
		// Accept both class and className programmatically to set domNode class.
		_getClass: getClass,
		_setClass: setClass,
		_getClassName: getClass,
		_setClassName: setClass,
		
		_setSort: function(property, descending){
			// summary:
			//		Sort the content
			// property: String|Array
			//		String specifying field to sort by, or actual array of objects
			//		with attribute and descending properties
			// descending: boolean
			//		In the case where property is a string, this argument
			//		specifies whether to sort ascending (false) or descending (true)
			
			this._sort = typeof property != "string" ? property :
				[{attribute: property, descending: descending}];
			
			this.refresh();
			
			if(this._lastCollection){
				if(property.length){
					// if an array was passed in, flatten to just first sort attribute
					// for default array sort logic
					if(typeof property != "string"){
						descending = property[0].descending;
						property = property[0].attribute;
					}
					
					this._lastCollection.sort(function(a,b){
						var aVal = a[property], bVal = b[property];
						// fall back undefined values to "" for more consistent behavior
						if(aVal === undefined){ aVal = ""; }
						if(bVal === undefined){ bVal = ""; }
						return aVal == bVal ? 0 : (aVal > bVal == !descending ? 1 : -1);
					});
				}
				this.renderArray(this._lastCollection);
			}
		},
		// TODO: remove the following two (and rename _sort to sort) in 0.4
		sort: function(property, descending){
			kernel.deprecated("sort(...)", 'use set("sort", ...) instead', "dgrid 0.4");
			this.set("sort", property, descending);
		},
		_getSort: function(){
			return this._sort;
		},
		
		_setShowHeader: function(show){
			// this is in List rather than just in Grid, primarily for two reasons:
			// (1) just in case someone *does* want to show a header in a List
			// (2) helps address IE < 8 header display issue in List
			
			var headerNode = this.headerNode;
			
			this.showHeader = show;
			
			// add/remove class which has styles for "hiding" header
			put(headerNode, (show ? "!" : ".") + "dgrid-header-hidden");
			
			this.renderHeader();
			this.resize(); // resize to account for (dis)appearance of header
			
			if(show){
				// Update scroll position of header to make sure it's in sync.
				headerNode.scrollLeft = this.getScrollPosition().x;
			}
		},
		setShowHeader: function(show){
			kernel.deprecated("setShowHeader(...)", 'use set("showHeader", ...) instead', "dgrid 0.4");
			this.set("showHeader", show);
		},
		
		_setShowFooter: function(show){
			this.showFooter = show;
			
			// add/remove class which has styles for hiding footer
			put(this.footerNode, (show ? "!" : ".") + "dgrid-footer-hidden");
			
			this.resize(); // to account for (dis)appearance of footer
		}
	});
});
