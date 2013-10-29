define(["../_StoreMixin", "dojo/_base/declare", "dojo/_base/array", "dojo/_base/lang", "dojo/_base/Deferred",
	"dojo/on", "dojo/query", "dojo/string", "dojo/has", "put-selector/put", "dojo/i18n!./nls/pagination",
	"dojo/_base/sniff", "xstyle/css!../css/extensions/Pagination.css"],
function(_StoreMixin, declare, arrayUtil, lang, Deferred, on, query, string, has, put, i18n){
	function cleanupContent(grid){
		// Remove any currently-rendered rows, or noDataMessage
		if(grid.noDataNode){
			put(grid.noDataNode, "!");
			delete grid.noDataNode;
		}else{
			grid.cleanup();
		}
		grid.contentNode.innerHTML = "";
	}
	function cleanupLoading(grid){
		if(grid.loadingNode){
			put(grid.loadingNode, "!");
			delete grid.loadingNode;
		}else if(grid._oldPageNodes){
			// If cleaning up after a load w/ showLoadingMessage: false,
			// be careful to only clean up rows from the old page, not the new one
			for(var id in grid._oldPageNodes){
				grid.removeRow(grid._oldPageNodes[id]);
			}
			delete grid._oldPageNodes;
			// Also remove the observer from the previous page, if there is one
			if(grid._oldPageObserver){
				grid._oldPageObserver.cancel();
				grid._numObservers--;
				delete grid._oldPageObserver;
			}
		}
		delete grid._isLoading;
	}
	
	return declare(_StoreMixin, {
		// summary:
		//		An extension for adding discrete pagination to a List or Grid.
		
		// rowsPerPage: Number
		//		Number of rows (items) to show on a given page.
		rowsPerPage: 10,
		
		// pagingTextBox: Boolean
		//		Indicates whether or not to show a textbox for paging.
		pagingTextBox: false,
		// previousNextArrows: Boolean
		//		Indicates whether or not to show the previous and next arrow links.
		previousNextArrows: true,
		// firstLastArrows: Boolean
		//		Indicates whether or not to show the first and last arrow links.
		firstLastArrows: false,
		
		// pagingLinks: Number
		//		The number of page links to show on each side of the current page
		//		Set to 0 (or false) to disable page links.
		pagingLinks: 2,
		// pageSizeOptions: Array[Number]
		//		This provides options for different page sizes in a drop-down.
		//		If it is empty (default), no page size drop-down will be displayed.
		pageSizeOptions: null,
		
		// showLoadingMessage: Boolean
		//		If true, clears previous data and displays loading node when requesting
		//		another page; if false, leaves previous data in place until new data
		//		arrives, then replaces it immediately.
		showLoadingMessage: true,
		
		// i18nPagination: Object
		//		This object contains all of the internationalized strings as
		//		key/value pairs.
		i18nPagination: i18n,
		
		showFooter: true,
		_currentPage: 1,
		_total: 0,
		
		buildRendering: function(){
			this.inherited(arguments);
			
			// add pagination to footer
			var grid = this,
				paginationNode = this.paginationNode =
					put(this.footerNode, "div.dgrid-pagination"),
				statusNode = this.paginationStatusNode =
					put(paginationNode, "div.dgrid-status"),
				i18n = this.i18nPagination,
				navigationNode,
				node,
				i;
			
			statusNode.tabIndex = 0;
			
			// Initialize UI based on pageSizeOptions and rowsPerPage
			this._updatePaginationSizeSelect();
			this._updateRowsPerPageOption();
			
			// initialize some content into paginationStatusNode, to ensure
			// accurate results on initial resize call
			statusNode.innerHTML = string.substitute(i18n.status,
				{ start: 1, end: 1, total: 0 });
			
			navigationNode = this.paginationNavigationNode =
				put(paginationNode, "div.dgrid-navigation");
			
			if(this.firstLastArrows){
				// create a first-page link
				node = this.paginationFirstNode =
					put(navigationNode,  "span.dgrid-first.dgrid-page-link", "«");
				node.setAttribute("aria-label", i18n.gotoFirst);
				node.tabIndex = 0;
			}
			if(this.previousNextArrows){
				// create a previous link
				node = this.paginationPreviousNode =
					put(navigationNode,  "span.dgrid-previous.dgrid-page-link", "‹");
				node.setAttribute("aria-label", i18n.gotoPrev);
				node.tabIndex = 0;
			}
			
			this.paginationLinksNode = put(navigationNode, "span.dgrid-pagination-links");
			if(this.previousNextArrows){
				// create a next link
				node = this.paginationNextNode =
					put(navigationNode, "span.dgrid-next.dgrid-page-link", "›");
				node.setAttribute("aria-label", i18n.gotoNext);
				node.tabIndex = 0;
			}
			if(this.firstLastArrows){
				// create a last-page link
				node = this.paginationLastNode =
					put(navigationNode,  "span.dgrid-last.dgrid-page-link", "»");
				node.setAttribute("aria-label", i18n.gotoLast);
				node.tabIndex = 0;
			}
			
			this._listeners.push(on(navigationNode, ".dgrid-page-link:click,.dgrid-page-link:keydown", function(event){
				// For keyboard events, only respond to enter
				if(event.type === "keydown" && event.keyCode !== 13){
					return;
				}
				
				var cls = this.className,
					curr, max;
				
				if(grid._isLoading || cls.indexOf("dgrid-page-disabled") > -1){
					return;
				}
				
				curr = grid._currentPage;
				max = Math.ceil(grid._total / grid.rowsPerPage);
				
				// determine navigation target based on clicked link's class
				if(this === grid.paginationPreviousNode){
					grid.gotoPage(curr - 1);
				}else if(this === grid.paginationNextNode){
					grid.gotoPage(curr + 1);
				}else if(this === grid.paginationFirstNode){
					grid.gotoPage(1);
				}else if(this === grid.paginationLastNode){
					grid.gotoPage(max);
				}else if(cls === "dgrid-page-link"){
					grid.gotoPage(+this.innerHTML, true); // the innerHTML has the page number
				}
			}));
		},
		
		destroy: function(){
			this.inherited(arguments);
			if(this._pagingTextBoxHandle){
				this._pagingTextBoxHandle.remove();
			}
		},

		_updatePaginationSizeSelect: function(){
			// summary:
			//		Creates or repopulates the pagination size selector based on
			//		the values in pageSizeOptions. Called from buildRendering
			//		and _setPageSizeOptions.
			
			var pageSizeOptions = this.pageSizeOptions,
				paginationSizeSelect = this.paginationSizeSelect,
				handle;
			
			if(pageSizeOptions && pageSizeOptions.length){
				if(!paginationSizeSelect){
					// First time setting page options; create the select
					paginationSizeSelect = this.paginationSizeSelect =
						put(this.paginationNode, "select.dgrid-page-size");
					
					handle = this._paginationSizeChangeHandle =
						on(paginationSizeSelect, "change", lang.hitch(this, function(){
							this.set("rowsPerPage", +this.paginationSizeSelect.value);
						}));
					this._listeners.push(handle);
				}
				
				// Repopulate options
				paginationSizeSelect.options.length = 0;
				for(i = 0; i < pageSizeOptions.length; i++){
					put(paginationSizeSelect, "option", pageSizeOptions[i], {
						value: pageSizeOptions[i],
						selected: this.rowsPerPage === pageSizeOptions[i]
					});
				}
				// Ensure current rowsPerPage value is in options
				this._updateRowsPerPageOption();
			}else if(!(pageSizeOptions && pageSizeOptions.length) && paginationSizeSelect){
				// pageSizeOptions was removed; remove/unhook the drop-down
				put(paginationSizeSelect, "!");
				this.paginationSizeSelect = null;
				this._paginationSizeChangeHandle.remove();
			}
		},

		_setPageSizeOptions: function(pageSizeOptions){
			this.pageSizeOptions = pageSizeOptions && pageSizeOptions.sort(function(a, b){
				return a - b;
			});
			this._updatePaginationSizeSelect();
		},

		_updateRowsPerPageOption: function(){
			// summary:
			//		Ensures that an option for rowsPerPage's value exists in the
			//		paginationSizeSelect drop-down (if one is rendered).
			//		Called from buildRendering and _setRowsPerPage.
			
			var rowsPerPage = this.rowsPerPage,
				pageSizeOptions = this.pageSizeOptions,
				paginationSizeSelect = this.paginationSizeSelect;
			
			if(paginationSizeSelect){
				if(arrayUtil.indexOf(pageSizeOptions, rowsPerPage) < 0){
					this._setPageSizeOptions(pageSizeOptions.concat([rowsPerPage])); 
				}else{
					paginationSizeSelect.value = "" + rowsPerPage;
				}
			}
		},
		
		_setRowsPerPage: function(rowsPerPage){
			this.rowsPerPage = rowsPerPage;
			this._updateRowsPerPageOption();
			this.gotoPage(1);
		},

		_updateNavigation: function(focusLink){
			// summary:
			//		Update status and navigation controls based on total count from query
			
			var grid = this,
				i18n = this.i18nPagination,
				linksNode = this.paginationLinksNode,
				currentPage = this._currentPage,
				pagingLinks = this.pagingLinks,
				paginationNavigationNode = this.paginationNavigationNode,
				end = Math.ceil(this._total / this.rowsPerPage),
				pagingTextBoxHandle = this._pagingTextBoxHandle;
			
			function pageLink(page, addSpace){
				var link;
				if(grid.pagingTextBox && page == currentPage && end > 1){
					// use a paging text box if enabled instead of just a number
					link = put(linksNode, 'input.dgrid-page-input[type=text][value=$]', currentPage);
					link.setAttribute("aria-label", i18n.jumpPage);
					grid._pagingTextBoxHandle = on(link, "change", function(){
						var value = +this.value;
						if(!isNaN(value) && value > 0 && value <= end){
							grid.gotoPage(+this.value, true);
						}
					});
				}else{
					// normal link
					link = put(linksNode,
						'span' + (page == currentPage ? '.dgrid-page-disabled' : '') + '.dgrid-page-link',
						page + (addSpace ? " " : ""));
					link.setAttribute("aria-label", i18n.gotoPage);
					link.tabIndex = 0;
				}
				if(page == currentPage && focusLink){
					// focus on it if we are supposed to retain the focus
					link.focus();
				}
			}
			
			if(pagingTextBoxHandle){ pagingTextBoxHandle.remove(); }
			linksNode.innerHTML = "";
			query(".dgrid-first, .dgrid-previous", paginationNavigationNode).forEach(function(link){
				put(link, (currentPage == 1 ? "." : "!") + "dgrid-page-disabled");
			});
			query(".dgrid-last, .dgrid-next", paginationNavigationNode).forEach(function(link){
				put(link, (currentPage >= end ? "." : "!") + "dgrid-page-disabled");
			});
			
			if(pagingLinks && end > 0){
				// always include the first page (back to the beginning)
				pageLink(1, true);
				var start = currentPage - pagingLinks;
				if(start > 2) {
					// visual indication of skipped page links
					put(linksNode, "span.dgrid-page-skip", "...");
				}else{
					start = 2;
				}
				// now iterate through all the page links we should show
				for(var i = start; i < Math.min(currentPage + pagingLinks + 1, end); i++){
					pageLink(i, true);
				}
				if(currentPage + pagingLinks + 1 < end){
					put(linksNode, "span.dgrid-page-skip", "...");
				}
				// last link
				if(end > 1){
					pageLink(end);
				}
			}else if(grid.pagingTextBox){
				// The pageLink function is also used to create the paging textbox.
				pageLink(currentPage);
			}
		},
		
		refresh: function(){
			var self = this;
			
			this.inherited(arguments);
			
			if(!this.store){
				console.warn("Pagination requires a store to operate.");
				return;
			}
			
			// Reset to first page and return promise from gotoPage
			return this.gotoPage(1).then(function(results){
				// Emit on a separate turn to enable event to be used consistently for
				// initial render, regardless of whether the backing store is async
				setTimeout(function() {
					on.emit(self.domNode, "dgrid-refresh-complete", {
						bubbles: true,
						cancelable: false,
						grid: self,
						results: results // QueryResults object (may be a wrapped promise)
					});
				}, 0);
				
				return results;
			});
		},
		
		_onNotification: function(rows){
			if(rows.length !== this._rowsOnPage){
				// Refresh the current page to maintain correct number of rows on page
				this.gotoPage(this._currentPage);
			}
		},
		
		renderArray: function(results, beforeNode){
			var grid = this,
				rows = this.inherited(arguments);
			
			// Make sure _lastCollection is cleared (due to logic in List)
			this._lastCollection = null;
			
			if(!beforeNode){
				if(this._topLevelRequest){
					// Cancel previous async request that didn't finish
					this._topLevelRequest.cancel();
					delete this._topLevelRequest;
				}
				
				if (typeof results.cancel === "function") {
					// Store reference to new async request in progress
					this._topLevelRequest = results;
				}
				
				Deferred.when(results, function(){
					if(grid._topLevelRequest){
						// Remove reference to request now that it's finished
						delete grid._topLevelRequest;
					}
				});
			}
			
			return rows;
		},
		
		insertRow: function(){
			var oldNodes = this._oldPageNodes,
				row = this.inherited(arguments);
			
			if(oldNodes && row === oldNodes[row.id]){
				// If the previous row was reused, avoid removing it in cleanup
				delete oldNodes[row.id];
			}
			
			return row;
		},
		
		gotoPage: function(page, focusLink){
			// summary:
			//		Loads the given page.  Note that page numbers start at 1.
			var grid = this,
				dfd = new Deferred();
			
			var result = this._trackError(function(){
				var count = grid.rowsPerPage,
					start = (page - 1) * count,
					options = lang.mixin(grid.get("queryOptions"), {
						start: start,
						count: count
						// current sort is also included by get("queryOptions")
					}),
					results,
					contentNode = grid.contentNode,
					loadingNode,
					oldNodes,
					children,
					i,
					len;
				
				if(grid.showLoadingMessage){
					cleanupContent(grid);
					loadingNode = grid.loadingNode = put(contentNode, "div.dgrid-loading");
					loadingNode.innerHTML = grid.loadingMessage;
				}else{
					// Reference nodes to be cleared later, rather than now;
					// iterate manually since IE < 9 doesn't like slicing HTMLCollections
					grid._oldPageNodes = oldNodes = {};
					children = contentNode.children;
					for(i = 0, len = children.length; i < len; i++){
						oldNodes[children[i].id] = children[i];
					}
					// Also reference the current page's observer (if any)
					grid._oldPageObserver = grid.observers.pop();
				}
				
				// set flag to deactivate pagination event handlers until loaded
				grid._isLoading = true;
				
				// Run new query and pass it into renderArray
				results = grid.store.query(grid.query, options);
				
				Deferred.when(grid.renderArray(results, null, options), function(rows){
					cleanupLoading(grid);
					// Reset scroll Y-position now that new page is loaded.
					grid.scrollTo({ y: 0 });
					
					Deferred.when(results.total, function(total){
						if(!total){
							if(grid.noDataNode){
								put(grid.noDataNode, "!");
								delete grid.noDataNode;
							}
							// If there are no results, display the no data message.
							grid.noDataNode = put(grid.contentNode, "div.dgrid-no-data");
							grid.noDataNode.innerHTML = grid.noDataMessage;
						}
						
						// Update status text based on now-current page and total.
						grid.paginationStatusNode.innerHTML = string.substitute(grid.i18nPagination.status, {
							start: Math.min(start + 1, total),
							end: Math.min(total, start + count),
							total: total
						});
						grid._total = total;
						grid._currentPage = page;
						grid._rowsOnPage = rows.length;
						
						// It's especially important that _updateNavigation is called only
						// after renderArray is resolved as well (to prevent jumping).
						grid._updateNavigation(focusLink);
					});
					
					if (has("ie") < 7 || (has("ie") && has("quirks"))) {
						// call resize in old IE in case grid is set to height: auto
						grid.resize();
					}
					
					dfd.resolve(results);
				}, function(error){
					cleanupLoading(grid);
					dfd.reject(error);
				});
				
				return dfd.promise;
			});
			
			if (!result) {
				// A synchronous error occurred; reject the promise.
				dfd.reject();
			}
			return dfd.promise;
		}
	});
});
