define([
	'../_StoreMixin',
	'dojo/_base/declare',
	'dojo/_base/array',
	'dojo/_base/lang',
	'dojo/on',
	'dojo/query',
	'dojo/string',
	'dojo/has',
	'dojo/when',
	'put-selector/put',
	'../util/misc',
	'dojo/i18n!./nls/pagination',
	'dojo/_base/sniff',
	'xstyle/css!../css/extensions/Pagination.css'
], function (_StoreMixin, declare, arrayUtil, lang, on, query, string, has, when, put, miscUtil, i18n) {
	function cleanupContent(grid) {
		// Remove any currently-rendered rows, or noDataMessage
		if (grid.noDataNode) {
			put(grid.noDataNode, '!');
			delete grid.noDataNode;
		}
		else {
			grid.cleanup();
		}
		grid.contentNode.innerHTML = '';
	}
	function cleanupLoading(grid) {
		if (grid.loadingNode) {
			put(grid.loadingNode, '!');
			delete grid.loadingNode;
		}
		else if (grid._oldPageNodes) {
			// If cleaning up after a load w/ showLoadingMessage: false,
			// be careful to only clean up rows from the old page, not the new one
			for (var id in grid._oldPageNodes) {
				grid.removeRow(grid._oldPageNodes[id]);
			}
			delete grid._oldPageNodes;
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

		buildRendering: function () {
			this.inherited(arguments);

			// add pagination to footer
			var grid = this,
				paginationNode = this.paginationNode =
					put(this.footerNode, 'div.dgrid-pagination'),
				statusNode = this.paginationStatusNode =
					put(paginationNode, 'div.dgrid-status'),
				i18n = this.i18nPagination,
				navigationNode,
				node;

			statusNode.tabIndex = 0;

			// Initialize UI based on pageSizeOptions and rowsPerPage
			this._updatePaginationSizeSelect();
			this._updateRowsPerPageOption();

			// initialize some content into paginationStatusNode, to ensure
			// accurate results on initial resize call
			this._updatePaginationStatus(this._total);

			navigationNode = this.paginationNavigationNode =
				put(paginationNode, 'div.dgrid-navigation');

			if (this.firstLastArrows) {
				// create a first-page link
				node = this.paginationFirstNode =
					put(navigationNode,  'span.dgrid-first.dgrid-page-link', '«');
				node.setAttribute('aria-label', i18n.gotoFirst);
				node.tabIndex = 0;
			}
			if (this.previousNextArrows) {
				// create a previous link
				node = this.paginationPreviousNode =
					put(navigationNode,  'span.dgrid-previous.dgrid-page-link', '‹');
				node.setAttribute('aria-label', i18n.gotoPrev);
				node.tabIndex = 0;
			}

			this.paginationLinksNode = put(navigationNode, 'span.dgrid-pagination-links');
			if (this.previousNextArrows) {
				// create a next link
				node = this.paginationNextNode =
					put(navigationNode, 'span.dgrid-next.dgrid-page-link', '›');
				node.setAttribute('aria-label', i18n.gotoNext);
				node.tabIndex = 0;
			}
			if (this.firstLastArrows) {
				// create a last-page link
				node = this.paginationLastNode =
					put(navigationNode,  'span.dgrid-last.dgrid-page-link', '»');
				node.setAttribute('aria-label', i18n.gotoLast);
				node.tabIndex = 0;
			}

			/* jshint maxlen: 121 */
			this._listeners.push(on(navigationNode, '.dgrid-page-link:click,.dgrid-page-link:keydown', function (event) {
				// For keyboard events, only respond to enter
				if (event.type === 'keydown' && event.keyCode !== 13) {
					return;
				}

				var cls = this.className,
					curr, max;

				if (grid._isLoading || cls.indexOf('dgrid-page-disabled') > -1) {
					return;
				}

				curr = grid._currentPage;
				max = Math.ceil(grid._total / grid.rowsPerPage);

				// determine navigation target based on clicked link's class
				if (this === grid.paginationPreviousNode) {
					grid.gotoPage(curr - 1);
				}
				else if (this === grid.paginationNextNode) {
					grid.gotoPage(curr + 1);
				}
				else if (this === grid.paginationFirstNode) {
					grid.gotoPage(1);
				}
				else if (this === grid.paginationLastNode) {
					grid.gotoPage(max);
				}
				else if (cls === 'dgrid-page-link') {
					grid.gotoPage(+this.innerHTML); // the innerHTML has the page number
				}
			}));
		},

		destroy: function () {
			this.inherited(arguments);
			if (this._pagingTextBoxHandle) {
				this._pagingTextBoxHandle.remove();
			}
		},

		_updatePaginationSizeSelect: function () {
			// summary:
			//		Creates or repopulates the pagination size selector based on
			//		the values in pageSizeOptions. Called from buildRendering
			//		and _setPageSizeOptions.

			var pageSizeOptions = this.pageSizeOptions,
				paginationSizeSelect = this.paginationSizeSelect,
				handle;

			if (pageSizeOptions && pageSizeOptions.length) {
				if (!paginationSizeSelect) {
					// First time setting page options; create the select
					paginationSizeSelect = this.paginationSizeSelect =
						put(this.paginationNode, 'select.dgrid-page-size[aria-label=' +
							this.i18nPagination.rowsPerPage + ']');

					handle = this._paginationSizeChangeHandle =
						on(paginationSizeSelect, 'change', lang.hitch(this, function () {
							this.set('rowsPerPage', +this.paginationSizeSelect.value);
						}));
					this._listeners.push(handle);
				}

				// Repopulate options
				paginationSizeSelect.options.length = 0;
				for (var i = 0; i < pageSizeOptions.length; i++) {
					put(paginationSizeSelect, 'option', pageSizeOptions[i], {
						value: pageSizeOptions[i],
						selected: this.rowsPerPage === pageSizeOptions[i]
					});
				}
				// Ensure current rowsPerPage value is in options
				this._updateRowsPerPageOption();
			}
			else if (!(pageSizeOptions && pageSizeOptions.length) && paginationSizeSelect) {
				// pageSizeOptions was removed; remove/unhook the drop-down
				put(paginationSizeSelect, '!');
				this.paginationSizeSelect = null;
				this._paginationSizeChangeHandle.remove();
			}
		},

		_setPageSizeOptions: function (pageSizeOptions) {
			this.pageSizeOptions = pageSizeOptions && pageSizeOptions.sort(function (a, b) {
				return a - b;
			});
			this._updatePaginationSizeSelect();
		},

		_updateRowsPerPageOption: function () {
			// summary:
			//		Ensures that an option for rowsPerPage's value exists in the
			//		paginationSizeSelect drop-down (if one is rendered).
			//		Called from buildRendering and _setRowsPerPage.

			var rowsPerPage = this.rowsPerPage,
				pageSizeOptions = this.pageSizeOptions,
				paginationSizeSelect = this.paginationSizeSelect;

			if (paginationSizeSelect) {
				if (arrayUtil.indexOf(pageSizeOptions, rowsPerPage) < 0) {
					this._setPageSizeOptions(pageSizeOptions.concat([rowsPerPage]));
				}
				else {
					paginationSizeSelect.value = '' + rowsPerPage;
				}
			}
		},

		_setRowsPerPage: function (rowsPerPage) {
			this.rowsPerPage = rowsPerPage;
			this._updateRowsPerPageOption();
			this.gotoPage(1);
		},

		_updateNavigation: function (total) {
			// summary:
			//		Update status and navigation controls based on total count from query

			var grid = this,
				i18n = this.i18nPagination,
				linksNode = this.paginationLinksNode,
				currentPage = this._currentPage,
				pagingLinks = this.pagingLinks,
				paginationNavigationNode = this.paginationNavigationNode,
				end = Math.ceil(total / this.rowsPerPage),
				pagingTextBoxHandle = this._pagingTextBoxHandle,
				focused = document.activeElement,
				focusedPage,
				lastFocusablePageLink,
				focusableNodes;

			function pageLink(page, addSpace) {
				var link;
				var disabled;
				if (grid.pagingTextBox && page === currentPage && end > 1) {
					// use a paging text box if enabled instead of just a number
					link = put(linksNode, 'input.dgrid-page-input[type=text][value=$]', currentPage);
					link.setAttribute('aria-label', i18n.jumpPage);
					grid._pagingTextBoxHandle = on(link, 'change', function () {
						var value = +this.value;
						if (!isNaN(value) && value > 0 && value <= end) {
							grid.gotoPage(+this.value);
						}
					});
					if (focused && focused.tagName === 'INPUT') {
						link.focus();
					}
				}
				else {
					// normal link
					disabled = page === currentPage;
					link = put(linksNode,
						'span' + (disabled ? '.dgrid-page-disabled' : '') + '.dgrid-page-link',
						page + (addSpace ? ' ' : ''));
					link.setAttribute('aria-label', i18n.gotoPage);
					link.tabIndex = disabled ? -1 : 0;

					// Try to restore focus if applicable;
					// if we need to but can't, try on the previous or next page,
					// depending on whether we're at the end
					if (focusedPage === page) {
						if (!disabled) {
							link.focus();
						}
						else if (page < end) {
							focusedPage++;
						}
						else {
							lastFocusablePageLink.focus();
						}
					}

					if (!disabled) {
						lastFocusablePageLink = link;
					}
				}
			}

			function setDisabled(link, disabled) {
				put(link, (disabled ? '.' : '!') + 'dgrid-page-disabled');
				link.tabIndex = disabled ? -1 : 0;
			}

			if (!focused || !this.paginationNavigationNode.contains(focused)) {
				focused = null;
			}
			else if (focused.className === 'dgrid-page-link') {
				focusedPage = +focused.innerHTML;
			}

			if (pagingTextBoxHandle) {
				pagingTextBoxHandle.remove();
			}
			linksNode.innerHTML = '';
			query('.dgrid-first, .dgrid-previous', paginationNavigationNode).forEach(function (link) {
				setDisabled(link, currentPage === 1);
			});
			query('.dgrid-last, .dgrid-next', paginationNavigationNode).forEach(function (link) {
				setDisabled(link, currentPage >= end);
			});

			if (pagingLinks && end > 0) {
				// always include the first page (back to the beginning)
				pageLink(1, true);
				var start = currentPage - pagingLinks;
				if (start > 2) {
					// visual indication of skipped page links
					put(linksNode, 'span.dgrid-page-skip', '...');
				}
				else {
					start = 2;
				}
				// now iterate through all the page links we should show
				for (var i = start; i < Math.min(currentPage + pagingLinks + 1, end); i++) {
					pageLink(i, true);
				}
				if (currentPage + pagingLinks + 1 < end) {
					put(linksNode, 'span.dgrid-page-skip', '...');
				}
				// last link
				if (end > 1) {
					pageLink(end);
				}
			}
			else if (grid.pagingTextBox) {
				// The pageLink function is also used to create the paging textbox.
				pageLink(currentPage);
			}

			if (focused && focused.tabIndex === -1) {
				// One of the first/last or prev/next links was focused but
				// is now disabled, so find something focusable
				focusableNodes = query('[tabindex="0"]', this.paginationNavigationNode);
				if (focused === this.paginationPreviousNode || focused === this.paginationFirstNode) {
					focused = focusableNodes[0];
				}
				else if (focusableNodes.length) {
					focused = focusableNodes[focusableNodes.length - 1];
				}
				if (focused) {
					focused.focus();
				}
			}
		},

		_updatePaginationStatus: function (total) {
			var count = this.rowsPerPage;
			var start = Math.min(total, (this._currentPage - 1) * count + 1);
			this.paginationStatusNode.innerHTML = string.substitute(this.i18nPagination.status, {
				start: start,
				end: Math.min(total, start + count - 1),
				total: total
			});
		},

		refresh: function (options) {
			// summary:
			//		Re-renders the first page of data, or the current page if
			//		options.keepCurrentPage is true.

			var self = this;
			var page = options && options.keepCurrentPage ?
				Math.min(this._currentPage, Math.ceil(this._total / this.rowsPerPage)) : 1;

			this.inherited(arguments);

			// Reset to first page and return promise from gotoPage
			return this.gotoPage(page).then(function (results) {
				// Emit on a separate turn to enable event to be used consistently for
				// initial render, regardless of whether the backing store is async
				setTimeout(function () {
					on.emit(self.domNode, 'dgrid-refresh-complete', {
						bubbles: true,
						cancelable: false,
						grid: self
					});
				}, 0);

				return results;
			});
		},

		_onNotification: function (rows, event, collection) {
			var rowsPerPage = this.rowsPerPage;
			var pageEnd = this._currentPage * rowsPerPage;
			var needsRefresh = (event.type === 'add' && event.index < pageEnd) ||
				(event.type === 'delete' && event.previousIndex < pageEnd) ||
				(event.type === 'update' &&
					Math.floor(event.index / rowsPerPage) !== Math.floor(event.previousIndex / rowsPerPage));

			if (needsRefresh) {
				// Refresh the current page to maintain correct number of rows on page
				this.gotoPage(Math.min(this._currentPage, Math.ceil(event.totalLength / this.rowsPerPage)) || 1);
			}
			// If we're not updating the whole page, check if we at least need to update status/navigation
			else if (collection === this._renderedCollection && event.totalLength !== this._total) {
				this._updatePaginationStatus(event.totalLength);
				this._updateNavigation(event.totalLength);
			}
		},

		renderQueryResults: function (results, beforeNode) {
			var grid = this,
				rows = this.inherited(arguments);

			if (!beforeNode) {
				if (this._topLevelRequest) {
					// Cancel previous async request that didn't finish
					this._topLevelRequest.cancel();
					delete this._topLevelRequest;
				}

				if (typeof rows.cancel === 'function') {
					// Store reference to new async request in progress
					this._topLevelRequest = rows;
				}

				rows.then(function () {
					if (grid._topLevelRequest) {
						// Remove reference to request now that it's finished
						delete grid._topLevelRequest;
					}
				});
			}

			return rows;
		},

		insertRow: function () {
			var oldNodes = this._oldPageNodes,
				row = this.inherited(arguments);

			if (oldNodes && row === oldNodes[row.id]) {
				// If the previous row was reused, avoid removing it in cleanup
				delete oldNodes[row.id];
			}

			return row;
		},

		gotoPage: function (page) {
			// summary:
			//		Loads the given page.  Note that page numbers start at 1.
			var grid = this,
				start = (this._currentPage - 1) * this.rowsPerPage;

			if (!this._renderedCollection) {
				console.warn('Pagination requires a collection to operate.');
				return when([]);
			}

			if (this._renderedCollection.releaseRange) {
				this._renderedCollection.releaseRange(start, start + this.rowsPerPage);
			}

			return this._trackError(function () {
				var count = grid.rowsPerPage,
					start = (page - 1) * count,
					options = {
						start: start,
						count: count
					},
					results,
					contentNode = grid.contentNode,
					loadingNode,
					oldNodes,
					children,
					i,
					len;

				if (grid.showLoadingMessage) {
					cleanupContent(grid);
					loadingNode = grid.loadingNode = put(contentNode, 'div.dgrid-loading');
					loadingNode.innerHTML = grid.loadingMessage;
				}
				else {
					// Reference nodes to be cleared later, rather than now;
					// iterate manually since IE < 9 doesn't like slicing HTMLCollections
					grid._oldPageNodes = oldNodes = {};
					children = contentNode.children;
					for (i = 0, len = children.length; i < len; i++) {
						oldNodes[children[i].id] = children[i];
					}
				}

				// set flag to deactivate pagination event handlers until loaded
				grid._isLoading = true;

				results = grid._renderedCollection.fetchRange({
					start: start,
					end: start + count
				});

				return grid.renderQueryResults(results, null, options).then(function (rows) {
					cleanupLoading(grid);
					// Reset scroll Y-position now that new page is loaded.
					grid.scrollTo({ y: 0 });

					if (grid._rows) {
						grid._rows.min = start;
						grid._rows.max = start + count - 1;
					}

					results.totalLength.then(function (total) {
						if (!total) {
							if (grid.noDataNode) {
								put(grid.noDataNode, '!');
								delete grid.noDataNode;
							}
							// If there are no results, display the no data message.
							grid.noDataNode = put(grid.contentNode, 'div.dgrid-no-data');
							grid.noDataNode.innerHTML = grid.noDataMessage;
						}

						// Update status text based on now-current page and total.
						grid._total = total;
						grid._currentPage = page;
						grid._rowsOnPage = rows.length;
						grid._updatePaginationStatus(total);

						// It's especially important that _updateNavigation is called only
						// after renderQueryResults is resolved as well (to prevent jumping).
						grid._updateNavigation(total);
					});

					return results;
				}, function (error) {
					cleanupLoading(grid);
					throw error;
				});
			});
		}
	});
});
