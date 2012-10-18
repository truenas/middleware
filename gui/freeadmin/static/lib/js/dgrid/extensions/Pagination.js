define(["../_StoreMixin", "dojo/_base/declare", "dojo/_base/lang", "dojo/_base/Deferred",
	"dojo/on", "dojo/query", "dojo/string", "dojo/has", "put-selector/put", "dojo/i18n!./nls/pagination",
	"dojo/_base/sniff", "xstyle/css!../css/extensions/Pagination.css"],
function(_StoreMixin, declare, lang, Deferred, on, query, string, has, put, i18n){
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
		pageSizeOptions: [],

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
				pageSizeOptions = this.pageSizeOptions,
				i18n = this.i18nPagination,
				navigationNode, node;
			
			statusNode.tabIndex = 0;
			
			if(pageSizeOptions.length){
				var sizeSelect = put(paginationNode, 'select.dgrid-page-size'),
					i;
				for(i = 0; i < pageSizeOptions.length; i++){
					put(sizeSelect, 'option', pageSizeOptions[i], {value: pageSizeOptions[i]});
				}
				on(sizeSelect, "change", function(){
					grid.rowsPerPage = +sizeSelect.value;
					grid.gotoPage(1);
				});
			}
			
			// initialize some content into paginationStatusNode, to ensure
			// accurate results on initial resize call
			statusNode.innerHTML = string.substitute(i18n.status,
				{ start: 1, end: 1, total: 0 });
			
			navigationNode = this.paginationNavigationNode =
				put(paginationNode, "div.dgrid-navigation");
			
			if(this.firstLastArrows){
				// create a first-page link
				node = put(navigationNode,  "a[href=javascript:].dgrid-first", "«");
				node.setAttribute("aria-label", i18n.gotoFirst);
			}
			if(this.previousNextArrows){
				// create a previous link
				node = put(navigationNode,  "a[href=javascript:].dgrid-previous", "‹");
				node.setAttribute("aria-label", i18n.gotoPrev);
			}
			
			this.paginationLinksNode = put(navigationNode, "span.dgrid-pagination-links");
			if(this.previousNextArrows){
				// create a next link
				node = put(navigationNode, "a[href=javascript:].dgrid-next", "›");
				node.setAttribute("aria-label", i18n.gotoNext);
			}
			if(this.firstLastArrows){
				// create a last-page link
				node = put(navigationNode,  "a[href=javascript:].dgrid-last", "»");
				node.setAttribute("aria-label", i18n.gotoLast);
			}
			
			on(navigationNode, "a:click", function(){
				var cls = this.className,
					curr, max;
				
				if(grid._isLoading || cls.indexOf("dgrid-page-disabled") > -1){
					return;
				}
				
				curr = grid._currentPage;
				max = Math.ceil(grid._total / grid.rowsPerPage);
				
				// determine navigation target based on clicked link's class
				if(cls == "dgrid-page-link"){
					grid.gotoPage(+this.innerHTML, true); // the innerHTML has the page number
				}else if(cls == "dgrid-first"){
					grid.gotoPage(1);
				}else if(cls == "dgrid-last"){
					grid.gotoPage(max);
				}else if(cls == "dgrid-previous"){
					grid.gotoPage(curr - 1);
				}else if(cls == "dgrid-next"){
					grid.gotoPage(curr + 1);
				}
			});
			
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
			
			function pageLink(page){
				var link;
				if(grid.pagingTextBox && page == currentPage){
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
						'a[href=javascript:]' + (page == currentPage ? '.dgrid-page-disabled' : '') + '.dgrid-page-link',
						page);
					link.setAttribute("aria-label", i18n.gotoPage);
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
				pageLink(1);
				var start = currentPage - pagingLinks;
				if(start > 2) {
					// visual indication of skipped page links
					put(linksNode, "span.dgrid-page-skip", "...");
				}else{
					start = 2;
				}
				// now iterate through all the page links we should show
				for(var i = start; i < Math.min(currentPage + pagingLinks + 1, end); i++){
					pageLink(i);
				}
				if(currentPage + pagingLinks + 1 < end){
					put(linksNode, "span.dgrid-page-skip", "...");
				}
				// last link
				pageLink(end);
			}else if(grid.pagingTextBox){
				// The pageLink function is also used to create the paging textbox.
				pageLink(currentPage);
			}
		},
		
		refresh: function(){
			if(!this.store){
				throw new Error("Pagination requires a store to operate.");
			}
			this.inherited(arguments);
			// reset to first page
			this.gotoPage(1);
		},
		
		gotoPage: function(page, focusLink){
			// summary:
			//		Loads the given page.  Note that page numbers start at 1.
			var grid = this;
			this._trackError(function(){
				var count = grid.rowsPerPage,
					start = (page - 1) * count,
					options = lang.mixin(grid.get("queryOptions"), {
						start: start,
						count: count
						// current sort is also included by get("queryOptions")
					}),
					results,
					contentNode = grid.contentNode,
					rows = grid._rowIdToObject,
					substrLen = 5 + grid.id.length, // trimmed from front of row IDs
					r, loadingNode;
				
				// remove any currently-rendered rows
				for(r in rows){
					grid.row(r.substr(substrLen)).remove();
				}
				grid._rowIdToObject = {};
				contentNode.innerHTML = "";
				
				loadingNode = put(contentNode, "div.dgrid-loading", grid.loadingMessage);
				
				// set flag to deactivate pagination event handlers until loaded
				grid._isLoading = true;
				
				// Run new query and pass it into renderArray
				results = grid.store.query(grid.query, options);
				
				return Deferred.when(grid.renderArray(results, loadingNode, options), function(){
					put(loadingNode, "!");
					delete grid._isLoading;
					// Reset scroll Y-position now that new page is loaded.
					grid.scrollTo({ y: 0 });
					
					Deferred.when(results.total, function(total){
						if(!total){
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
						
						// It's especially important that _updateNavigation is called only
						// after renderArray is resolved as well (to prevent jumping).
						grid._updateNavigation(focusLink);
					});
					
					if (has("ie") < 7 || (has("ie") && has("quirks"))) {
						// call resize in old IE in case grid is set to height: auto
						grid.resize();
					}
				}, function(error){
					// enable loading again before throwing the error
					delete grid._isLoading;
					throw error;
				});
			});
		}
	});
});
