define([
	'dojo/_base/declare',
	'dojo/_base/lang',
	'dojo/_base/array',
	'dojo/aspect',
	'dojo/on',
	'dojo/query',
	'dojo/when',
	'./util/has-css3',
	'./Grid',
	'dojo/has!touch?./util/touch',
	'put-selector/put'
], function (declare, lang, arrayUtil, aspect, on, querySelector, when, has, Grid, touchUtil, put) {

	return declare(null, {
		// collapseOnRefresh: Boolean
		//		Whether to collapse all expanded nodes any time refresh is called.
		collapseOnRefresh: false,

		// enableTreeTransitions: Boolean
		//		Enables/disables all expand/collapse CSS transitions.
		enableTreeTransitions: true,

		// treeIndentWidth: Number
		//		Width (in pixels) of each level of indentation.
		treeIndentWidth: 9,

		constructor: function () {
			this._treeColumnListeners = [];
		},

		shouldExpand: function (row, level, previouslyExpanded) {
			// summary:
			//		Function called after each row is inserted to determine whether
			//		expand(rowElement, true) should be automatically called.
			//		The default implementation re-expands any rows that were expanded
			//		the last time they were rendered (if applicable).

			return previouslyExpanded;
		},

		expand: function (target, expand, noTransition) {
			// summary:
			//		Expands the row corresponding to the given target.
			// target: Object
			//		Row object (or something resolvable to one) to expand/collapse.
			// expand: Boolean?
			//		If specified, designates whether to expand or collapse the row;
			//		if unspecified, toggles the current state.

			if (!this._treeColumn) {
				return;
			}

			var grid = this,
				row = target.element ? target : this.row(target),
				isExpanded = !!this._expanded[row.id],
				hasTransitionend = has('transitionend'),
				promise;

			target = row.element;
			target = target.className.indexOf('dgrid-expando-icon') > -1 ? target :
				querySelector('.dgrid-expando-icon', target)[0];

			noTransition = noTransition || !this.enableTreeTransitions;

			if (target && target.mayHaveChildren && (noTransition || expand !== isExpanded)) {
				// toggle or set expand/collapsed state based on optional 2nd argument
				var expanded = expand === undefined ? !this._expanded[row.id] : expand;

				// update the expando display
				put(target, '.ui-icon-triangle-1-' + (expanded ? 'se' : 'e') +
					'!ui-icon-triangle-1-' + (expanded ? 'e' : 'se'));
				put(row.element, (expanded ? '.' : '!') + 'dgrid-row-expanded');

				var rowElement = row.element,
					container = rowElement.connected,
					containerStyle,
					scrollHeight,
					options = {};

				if (!container) {
					// if the children have not been created, create a container, a preload node and do the
					// query for the children
					container = options.container = rowElement.connected =
						put(rowElement, '+div.dgrid-tree-container');
					var query = function (options) {
						var childCollection = grid._renderedCollection.getChildren(row.data),
							results;
						if (grid.sort && grid.sort.length > 0) {
							childCollection = childCollection.sort(grid.sort);
						}
						if (childCollection.track && grid.shouldTrackCollection) {
							container._rows = options.rows = [];

							childCollection = childCollection.track();

							// remember observation handles so they can be removed when the parent row is destroyed
							container._handles = [
								childCollection.tracking,
								grid._observeCollection(childCollection, container, options)
							];
						}
						if ('start' in options) {
							var rangeArgs = {
								start: options.start,
								end: options.start + options.count
							};
							results = childCollection.fetchRange(rangeArgs);
						} else {
							results = childCollection.fetch();
						}
						return results;
					};
					// Include level information on query for renderQuery case
					if ('level' in target) {
						query.level = target.level;
					}

					// Add the query to the promise chain
					if (this.renderQuery) {
						promise = this.renderQuery(query, options);
					}
					else {
						// If not using OnDemandList, we don't need preload nodes,
						// but we still need a beforeNode to pass to renderArray,
						// so create a temporary one
						var firstChild = put(container, 'div');
						promise = this._trackError(function () {
							return grid.renderQueryResults(
								query(options),
								firstChild,
								lang.mixin({ rows: options.rows },
									'level' in query ? { queryLevel: query.level } : null
								)
							).then(function (rows) {
								put(firstChild, '!');
								return rows;
							});
						});
					}

					if (hasTransitionend) {
						// Update height whenever a collapse/expand transition ends.
						// (This handler is only registered when each child container is first created.)
						on(container, hasTransitionend, this._onTreeTransitionEnd);
					}
				}

				// Show or hide all the children.

				container.hidden = !expanded;
				containerStyle = container.style;

				// make sure it is visible so we can measure it
				if (!hasTransitionend || noTransition) {
					containerStyle.display = expanded ? 'block' : 'none';
					containerStyle.height = '';
				}
				else {
					if (expanded) {
						containerStyle.display = 'block';
						scrollHeight = container.scrollHeight;
						containerStyle.height = '0px';
					}
					else {
						// if it will be hidden we need to be able to give a full height
						// without animating it, so it has the right starting point to animate to zero
						put(container, '.dgrid-tree-resetting');
						containerStyle.height = container.scrollHeight + 'px';
					}
					// Perform a transition for the expand or collapse.
					setTimeout(function () {
						put(container, '!dgrid-tree-resetting');
						containerStyle.height =
							expanded ? (scrollHeight ? scrollHeight + 'px' : 'auto') : '0px';
					}, 0);
				}

				// Update _expanded map.
				if (expanded) {
					this._expanded[row.id] = true;
				}
				else {
					delete this._expanded[row.id];
				}
			}

			// Always return a promise
			return when(promise);
		},

		_configColumns: function () {
			var columnArray = this.inherited(arguments);

			// Set up hash to store IDs of expanded rows (here rather than in
			// _configureTreeColumn so nothing breaks if no column has renderExpando)
			this._expanded = {};

			for (var i = 0, l = columnArray.length; i < l; i++) {
				if (columnArray[i].renderExpando) {
					this._configureTreeColumn(columnArray[i]);
					break; // Allow only one tree column.
				}
			}
			return columnArray;
		},

		insertRow: function (object) {
			var rowElement = this.inherited(arguments);

			// Auto-expand (shouldExpand) considerations
			var row = this.row(rowElement),
				expanded = this.shouldExpand(row, this._currentLevel, this._expanded[row.id]);

			if (expanded) {
				this.expand(rowElement, true, true);
			}

			if (expanded || (!this.collection.mayHaveChildren || this.collection.mayHaveChildren(object))) {
				put(rowElement, '.dgrid-row-expandable');
			}

			return rowElement; // pass return value through
		},

		removeRow: function (rowElement, preserveDom) {
			var connected = rowElement.connected,
				childOptions = {};
			if (connected) {
				if (connected._handles) {
					arrayUtil.forEach(connected._handles, function (handle) {
						handle.remove();
					});
					delete connected._handles;
				}

				if (connected._rows) {
					childOptions.rows = connected._rows;
				}

				querySelector('>.dgrid-row', connected).forEach(function (element) {
					this.removeRow(element, true, childOptions);
				}, this);

				if (connected._rows) {
					connected._rows.length = 0;
					delete connected._rows;
				}

				if (!preserveDom) {
					put(connected, '!');
				}
			}

			this.inherited(arguments);
		},

		cleanup: function () {
			this.inherited(arguments);

			if (this.collapseOnRefresh) {
				// Clear out the _expanded hash on each call to cleanup
				// (which generally coincides with refreshes, as well as destroy)
				this._expanded = {};
			}
		},

		_destroyColumns: function () {
			var listeners = this._treeColumnListeners;

			for (var i = listeners.length; i--;) {
				listeners[i].remove();
			}
			this._treeColumnListeners = [];
			this._treeColumn = null;
		},

		_calcRowHeight: function (rowElement) {
			// Override this method to provide row height measurements that
			// include the children of a row
			var connected = rowElement.connected;
			// if connected, need to consider this in the total row height
			return this.inherited(arguments) + (connected ? connected.offsetHeight : 0);
		},

		_configureTreeColumn: function (column) {
			// summary:
			//		Adds tree navigation capability to a column.

			var grid = this;
			var colSelector = '.dgrid-content .dgrid-column-' + column.id;
			var clicked; // tracks row that was clicked (for expand dblclick event handling)

			this._treeColumn = column;
			if (!column._isConfiguredTreeColumn) {
				var originalRenderCell = column.renderCell || this._defaultRenderCell;
				column._isConfiguredTreeColumn = true;
				column.renderCell = function (object, value, td, options) {
					// summary:
					//		Renders a cell that can be expanded, creating more rows

					var level = Number(options && options.queryLevel) + 1,
						mayHaveChildren = !grid.collection.mayHaveChildren || grid.collection.mayHaveChildren(object),
						expando, node;

					level = grid._currentLevel = isNaN(level) ? 0 : level;
					expando = column.renderExpando(level, mayHaveChildren,
						grid._expanded[grid.collection.getIdentity(object)], object);
					expando.level = level;
					expando.mayHaveChildren = mayHaveChildren;

					node = originalRenderCell.call(column, object, value, td, options);
					if (node && node.nodeType) {
						put(td, expando);
						put(td, node);
					}
					else {
						td.insertBefore(expando, td.firstChild);
					}
				};

				if (typeof column.renderExpando !== 'function') {
					column.renderExpando = this._defaultRenderExpando;
				}
			}

			var treeColumnListeners = this._treeColumnListeners;
			if (treeColumnListeners.length === 0) {
				// Set up the event listener once and use event delegation for better memory use.
				treeColumnListeners.push(this.on(column.expandOn ||
					'.dgrid-expando-icon:click,' + colSelector + ':dblclick,' + colSelector + ':keydown',
					function (event) {
						var row = grid.row(event);
						if ((!grid.collection.mayHaveChildren || grid.collection.mayHaveChildren(row.data)) &&
							(event.type !== 'keydown' || event.keyCode === 32) && !(event.type === 'dblclick' &&
							clicked && clicked.count > 1 && row.id === clicked.id &&
							event.target.className.indexOf('dgrid-expando-icon') > -1)) {
							grid.expand(row);
						}

						// If the expando icon was clicked, update clicked object to prevent
						// potential over-triggering on dblclick (all tested browsers but IE < 9).
						if (event.target.className.indexOf('dgrid-expando-icon') > -1) {
							if (clicked && clicked.id === grid.row(event).id) {
								clicked.count++;
							}
							else {
								clicked = {
									id: grid.row(event).id,
									count: 1
								};
							}
						}
					})
				);

				if (has('touch')) {
					// Also listen on double-taps of the cell.
					treeColumnListeners.push(this.on(touchUtil.selector(colSelector, touchUtil.dbltap),
						function () {
							grid.expand(this);
						}));
				}
			}
		},

		_defaultRenderExpando: function (level, hasChildren, expanded) {
			// summary:
			//		Default implementation for column.renderExpando.
			//		NOTE: Called in context of the column definition object.
			// level: Number
			//		Level of indentation for this row (0 for top-level)
			// hasChildren: Boolean
			//		Whether this item may have children (in most cases this determines
			//		whether an expando icon should be rendered)
			// expanded: Boolean
			//		Whether this item is currently in expanded state
			// object: Object
			//		The item that this expando pertains to

			var dir = this.grid.isRTL ? 'right' : 'left',
				cls = '.dgrid-expando-icon',
				node;
			if (hasChildren) {
				cls += '.ui-icon.ui-icon-triangle-1-' + (expanded ? 'se' : 'e');
			}
			node = put('div' + cls + '[style=margin-' + dir + ': ' +
				(level * this.grid.treeIndentWidth) + 'px; float: ' + dir + ']');
			node.innerHTML = '&nbsp;';
			return node;
		},

		_onNotification: function (rows, event) {
			if (event.type === 'delete') {
				delete this._expanded[event.id];
			}
			this.inherited(arguments);
		},

		_onTreeTransitionEnd: function (event) {
			var container = this,
				height = this.style.height;
			if (height) {
				// After expansion, ensure display is correct;
				// after collapse, set display to none to improve performance
				this.style.display = height === '0px' ? 'none' : 'block';
			}

			// Reset height to be auto, so future height changes (from children
			// expansions, for example), will expand to the right height.
			if (event) {
				// For browsers with CSS transition support, setting the height to
				// auto or "" will cause an animation to zero height for some
				// reason, so temporarily set the transition to be zero duration
				put(this, '.dgrid-tree-resetting');
				setTimeout(function () {
					// Turn off the zero duration transition after we have let it render
					put(container, '!dgrid-tree-resetting');
				}, 0);
			}
			// Now set the height to auto
			this.style.height = '';
		}
	});
});
