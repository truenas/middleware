define([
	'dojo/_base/declare',
	'dojo/aspect',
	'dojo/on',
	'dojo/_base/lang',
	'dojo/has',
	'put-selector/put',
	'./util/misc',
	'dojo/_base/sniff'
], function (declare, aspect, on, lang, has, put, miscUtil) {

	var delegatingInputTypes = {
			checkbox: 1,
			radio: 1,
			button: 1
		},
		hasGridCellClass = /\bdgrid-cell\b/,
		hasGridRowClass = /\bdgrid-row\b/;

	var Keyboard = declare(null, {
		// summary:
		//		Adds keyboard navigation capability to a list or grid.

		// pageSkip: Number
		//		Number of rows to jump by when page up or page down is pressed.
		pageSkip: 10,

		tabIndex: 0,

		// keyMap: Object
		//		Hash which maps key codes to functions to be executed (in the context
		//		of the instance) for key events within the grid's body.
		keyMap: null,

		// headerKeyMap: Object
		//		Hash which maps key codes to functions to be executed (in the context
		//		of the instance) for key events within the grid's header row.
		headerKeyMap: null,

		postMixInProperties: function () {
			this.inherited(arguments);

			if (!this.keyMap) {
				this.keyMap = lang.mixin({}, Keyboard.defaultKeyMap);
			}
			if (!this.headerKeyMap) {
				this.headerKeyMap = lang.mixin({}, Keyboard.defaultHeaderKeyMap);
			}
		},

		postCreate: function () {
			this.inherited(arguments);
			var grid = this;

			function handledEvent(event) {
				// Text boxes and other inputs that can use direction keys should be ignored
				// and not affect cell/row navigation
				var target = event.target;
				return target.type && (!delegatingInputTypes[target.type] || event.keyCode === 32);
			}

			function enableNavigation(areaNode) {
				var cellNavigation = grid.cellNavigation,
					isFocusableClass = cellNavigation ? hasGridCellClass : hasGridRowClass,
					isHeader = areaNode === grid.headerNode,
					initialNode = areaNode;

				function initHeader() {
					if (grid._focusedHeaderNode) {
						// Remove the tab index for the node that previously had it.
						grid._focusedHeaderNode.tabIndex = -1;
					}
					if (grid.showHeader) {
						if (cellNavigation) {
							// Get the focused element. Ensure that the focused element
							// is actually a grid cell, not a column-set-cell or some
							// other cell that should not be focused
							var elements = grid.headerNode.getElementsByTagName('th');
							for (var i = 0, element; (element = elements[i]); ++i) {
								if (isFocusableClass.test(element.className)) {
									grid._focusedHeaderNode = initialNode = element;
									break;
								}
							}
						}
						else {
							grid._focusedHeaderNode = initialNode = grid.headerNode;
						}

						// Set the tab index only if the header is visible.
						if (initialNode) {
							initialNode.tabIndex = grid.tabIndex;
						}
					}
				}

				function afterContentAdded() {
					// Ensures the first element of a grid is always keyboard selectable after data has been
					// retrieved if there is not already a valid focused element.

					var focusedNode = grid._focusedNode || initialNode;

					// do not update the focused element if we already have a valid one
					if (isFocusableClass.test(focusedNode.className) && areaNode.contains(focusedNode)) {
						return;
					}

					// ensure that the focused element is actually a grid cell, not a
					// dgrid-preload or dgrid-content element, which should not be focusable,
					// even when data is loaded asynchronously
					var elements = areaNode.getElementsByTagName('*');
					for (var i = 0, element; (element = elements[i]); ++i) {
						if (isFocusableClass.test(element.className)) {
							focusedNode = grid._focusedNode = element;
							break;
						}
					}

					initialNode.tabIndex = -1;
					focusedNode.tabIndex = grid.tabIndex; // This is initialNode if nothing focusable was found
					return;
				}

				if (isHeader) {
					// Initialize header now (since it's already been rendered),
					// and aspect after future renderHeader calls to reset focus.
					initHeader();
					aspect.after(grid, 'renderHeader', initHeader, true);
				}
				else {
					aspect.after(grid, 'renderArray', afterContentAdded, true);
					aspect.after(grid, '_onNotification', function (rows, event) {
						if (event.totalLength === 0) {
							areaNode.tabIndex = 0;
						}
						else if (event.totalLength === 1 && event.type === 'add') {
							afterContentAdded();
						}
					}, true);
				}

				grid._listeners.push(on(areaNode, 'mousedown', function (event) {
					if (!handledEvent(event)) {
						grid._focusOnNode(event.target, isHeader, event);
					}
				}));

				grid._listeners.push(on(areaNode, 'keydown', function (event) {
					// For now, don't squash browser-specific functionalities by letting
					// ALT and META function as they would natively
					if (event.metaKey || event.altKey) {
						return;
					}

					var handler = grid[isHeader ? 'headerKeyMap' : 'keyMap'][event.keyCode];

					// Text boxes and other inputs that can use direction keys should be ignored
					// and not affect cell/row navigation
					if (handler && !handledEvent(event)) {
						handler.call(grid, event);
					}
				}));
			}

			if (this.tabableHeader) {
				enableNavigation(this.headerNode);
				on(this.headerNode, 'dgrid-cellfocusin', function () {
					grid.scrollTo({ x: this.scrollLeft });
				});
			}
			enableNavigation(this.contentNode);

			this._debouncedEnsureScroll = miscUtil.debounce(this._ensureScroll, this);
		},

		removeRow: function (rowElement) {
			if (!this._focusedNode) {
				// Nothing special to do if we have no record of anything focused
				return this.inherited(arguments);
			}

			var self = this,
				isActive = document.activeElement === this._focusedNode,
				focusedTarget = this[this.cellNavigation ? 'cell' : 'row'](this._focusedNode),
				focusedRow = focusedTarget.row || focusedTarget,
				sibling;
			rowElement = rowElement.element || rowElement;

			// If removed row previously had focus, temporarily store information
			// to be handled in an immediately-following insertRow call, or next turn
			if (rowElement === focusedRow.element) {
				sibling = this.down(focusedRow, true);

				// Check whether down call returned the same row, or failed to return
				// any (e.g. during a partial unrendering)
				if (!sibling || sibling.element === rowElement) {
					sibling = this.up(focusedRow, true);
				}

				this._removedFocus = {
					active: isActive,
					rowId: focusedRow.id,
					columnId: focusedTarget.column && focusedTarget.column.id,
					siblingId: !sibling || sibling.element === rowElement ? undefined : sibling.id
				};

				// Call _restoreFocus on next turn, to restore focus to sibling
				// if no replacement row was immediately inserted.
				// Pass original row's id in case it was re-inserted in a renderArray
				// call (and thus was found, but couldn't be focused immediately)
				setTimeout(function () {
					if (self._removedFocus) {
						self._restoreFocus(focusedRow.id);
					}
				}, 0);

				// Clear _focusedNode until _restoreFocus is called, to avoid
				// needlessly re-running this logic
				this._focusedNode = null;
			}

			this.inherited(arguments);
		},

		insertRow: function () {
			var rowElement = this.inherited(arguments);
			if (this._removedFocus && !this._removedFocus.wait) {
				this._restoreFocus(rowElement);
			}
			return rowElement;
		},

		_restoreFocus: function (row) {
			// summary:
			//		Restores focus to the newly inserted row if it matches the
			//		previously removed row, or to the nearest sibling otherwise.

			var focusInfo = this._removedFocus,
				newTarget,
				cell;

			row = row && this.row(row);
			newTarget = row && row.element && row.id === focusInfo.rowId ? row :
				typeof focusInfo.siblingId !== 'undefined' && this.row(focusInfo.siblingId);

			if (newTarget && newTarget.element) {
				if (!newTarget.element.parentNode.parentNode) {
					// This was called from renderArray, so the row hasn't
					// actually been placed in the DOM yet; handle it on the next
					// turn (called from removeRow).
					focusInfo.wait = true;
					return;
				}
				// Should focus be on a cell?
				if (typeof focusInfo.columnId !== 'undefined') {
					cell = this.cell(newTarget, focusInfo.columnId);
					if (cell && cell.element) {
						newTarget = cell;
					}
				}
				if (focusInfo.active && newTarget.element.offsetHeight !== 0) {
					// Row/cell was previously focused and is visible, so focus the new one immediately
					this._focusOnNode(newTarget, false, null);
				}
				else {
					// Row/cell was not focused or is not visible, but we still need to
					// update _focusedNode and the element's tabIndex/class
					put(newTarget.element, '.dgrid-focus');
					newTarget.element.tabIndex = this.tabIndex;
					this._focusedNode = newTarget.element;
				}
			}

			delete this._removedFocus;
		},

		addKeyHandler: function (key, callback, isHeader) {
			// summary:
			//		Adds a handler to the keyMap on the instance.
			//		Supports binding additional handlers to already-mapped keys.
			// key: Number
			//		Key code representing the key to be handled.
			// callback: Function
			//		Callback to be executed (in instance context) when the key is pressed.
			// isHeader: Boolean
			//		Whether the handler is to be added for the grid body (false, default)
			//		or the header (true).

			// Aspects may be about 10% slower than using an array-based appraoch,
			// but there is significantly less code involved (here and above).
			return aspect.after( // Handle
				this[isHeader ? 'headerKeyMap' : 'keyMap'], key, callback, true);
		},

		_ensureRowScroll: function (rowElement) {
			// summary:
			//		Ensures that the entire row is visible within the viewport.
			//		Called for cell navigation in complex structures.

			var scrollY = this.getScrollPosition().y;
			if (scrollY > rowElement.offsetTop) {
				// Row starts above the viewport
				this.scrollTo({ y: rowElement.offsetTop });
			}
			else if (scrollY + this.contentNode.offsetHeight < rowElement.offsetTop + rowElement.offsetHeight) {
				// Row ends below the viewport
				this.scrollTo({ y: rowElement.offsetTop - this.contentNode.offsetHeight + rowElement.offsetHeight });
			}
		},

		_ensureColumnScroll: function (cellElement) {
			// summary:
			//		Ensures that the entire cell is visible in the viewport.
			//		Called in cases where the grid can scroll horizontally.

			var scrollX = this.getScrollPosition().x;
			var cellLeft = cellElement.offsetLeft;
			if (scrollX > cellLeft) {
				this.scrollTo({ x: cellLeft });
			}
			else {
				var bodyWidth = this.bodyNode.clientWidth;
				var cellWidth = cellElement.offsetWidth;
				var cellRight = cellLeft + cellWidth;
				if (scrollX + bodyWidth < cellRight) {
					// Adjust so that the right side of the cell and grid body align,
					// unless the cell is actually wider than the body - then align the left sides
					this.scrollTo({ x: bodyWidth > cellWidth ? cellRight - bodyWidth : cellLeft });
				}
			}
		},

		_ensureScroll: function (cell, isHeader) {
			// summary:
			//		Corrects scroll based on the position of the newly-focused row/cell
			//		as necessary based on grid configuration and dimensions.

			if(this.cellNavigation && (this.columnSets || this.subRows.length > 1) && !isHeader){
				this._ensureRowScroll(cell.row.element);
			}
			if(this.bodyNode.clientWidth < this.contentNode.offsetWidth){
				this._ensureColumnScroll(cell.element);
			}
		},

		_focusOnNode: function (element, isHeader, event) {
			var focusedNodeProperty = '_focused' + (isHeader ? 'Header' : '') + 'Node',
				focusedNode = this[focusedNodeProperty],
				cellOrRowType = this.cellNavigation ? 'cell' : 'row',
				cell = this[cellOrRowType](element),
				inputs,
				input,
				numInputs,
				inputFocused,
				i;

			element = cell && cell.element;
			if (!element) {
				return;
			}

			if (this.cellNavigation) {
				inputs = element.getElementsByTagName('input');
				for (i = 0, numInputs = inputs.length; i < numInputs; i++) {
					input = inputs[i];
					if ((input.tabIndex !== -1 || '_dgridLastValue' in input) && !input.disabled) {
						input.focus();
						inputFocused = true;
						break;
					}
				}
			}

			// Set up event information for dgrid-cellfocusout/in events.
			// Note that these events are not fired for _restoreFocus.
			if (event !== null) {
				event = lang.mixin({ grid: this }, event);
				if (event.type) {
					event.parentType = event.type;
				}
				if (!event.bubbles) {
					// IE doesn't always have a bubbles property already true.
					// Opera throws if you try to set it to true if it is already true.
					event.bubbles = true;
				}
			}

			if (focusedNode) {
				// Clean up previously-focused element
				// Remove the class name and the tabIndex attribute
				put(focusedNode, '!dgrid-focus[!tabIndex]');

				// Expose object representing focused cell or row losing focus, via
				// event.cell or event.row; which is set depends on cellNavigation.
				if (event) {
					event[cellOrRowType] = this[cellOrRowType](focusedNode);
					on.emit(focusedNode, 'dgrid-cellfocusout', event);
				}
			}
			focusedNode = this[focusedNodeProperty] = element;

			if (event) {
				// Expose object representing focused cell or row gaining focus, via
				// event.cell or event.row; which is set depends on cellNavigation.
				// Note that yes, the same event object is being reused; on.emit
				// performs a shallow copy of properties into a new event object.
				event[cellOrRowType] = cell;
			}

			var isFocusableClass = this.cellNavigation ? hasGridCellClass : hasGridRowClass;
			if (!inputFocused && isFocusableClass.test(element.className)) {
				element.tabIndex = this.tabIndex;
				element.focus();
			}
			put(element, '.dgrid-focus');

			if (event) {
				on.emit(focusedNode, 'dgrid-cellfocusin', event);
			}

			this._debouncedEnsureScroll(cell, isHeader);
		},

		focusHeader: function (element) {
			this._focusOnNode(element || this._focusedHeaderNode, true);
		},

		focus: function (element) {
			var node = element || this._focusedNode;
			if (node) {
				this._focusOnNode(node, false);
			}
			else {
				if (this._removedFocus) {
					this._removedFocus.active = true;
				}
				this.contentNode.focus();
			}
		}
	});

	// Common functions used in default keyMap (called in instance context)

	var moveFocusVertical = Keyboard.moveFocusVertical = function (event, steps) {
		var cellNavigation = this.cellNavigation,
			target = this[cellNavigation ? 'cell' : 'row'](event),
			columnId = cellNavigation && target.column.id,
			next = this.down(this._focusedNode, steps, true);

		// Navigate within same column if cell navigation is enabled
		if (cellNavigation) {
			next = this.cell(next, columnId);
		}
		this._focusOnNode(next, false, event);

		event.preventDefault();
	};

	var moveFocusUp = Keyboard.moveFocusUp = function (event) {
		moveFocusVertical.call(this, event, -1);
	};

	var moveFocusDown = Keyboard.moveFocusDown = function (event) {
		moveFocusVertical.call(this, event, 1);
	};

	var moveFocusPageUp = Keyboard.moveFocusPageUp = function (event) {
		moveFocusVertical.call(this, event, -this.pageSkip);
	};

	var moveFocusPageDown = Keyboard.moveFocusPageDown = function (event) {
		moveFocusVertical.call(this, event, this.pageSkip);
	};

	var moveFocusHorizontal = Keyboard.moveFocusHorizontal = function (event, steps) {
		if (!this.cellNavigation) {
			return;
		}
		var isHeader = !this.row(event), // header reports row as undefined
			currentNode = this['_focused' + (isHeader ? 'Header' : '') + 'Node'];

		this._focusOnNode(this.right(currentNode, steps), isHeader, event);
		event.preventDefault();
	};

	var moveFocusLeft = Keyboard.moveFocusLeft = function (event) {
		moveFocusHorizontal.call(this, event, -1);
	};

	var moveFocusRight = Keyboard.moveFocusRight = function (event) {
		moveFocusHorizontal.call(this, event, 1);
	};

	var moveHeaderFocusEnd = Keyboard.moveHeaderFocusEnd = function (event, scrollToBeginning) {
		// Header case is always simple, since all rows/cells are present
		var nodes;
		if (this.cellNavigation) {
			nodes = this.headerNode.getElementsByTagName('th');
			this._focusOnNode(nodes[scrollToBeginning ? 0 : nodes.length - 1], true, event);
		}
		// In row-navigation mode, there's nothing to do - only one row in header

		// Prevent browser from scrolling entire page
		event.preventDefault();
	};

	var moveHeaderFocusHome = Keyboard.moveHeaderFocusHome = function (event) {
		moveHeaderFocusEnd.call(this, event, true);
	};

	var moveFocusEnd = Keyboard.moveFocusEnd = function (event, scrollToTop) {
		// summary:
		//		Handles requests to scroll to the beginning or end of the grid.

		var cellNavigation = this.cellNavigation,
			contentNode = this.contentNode,
			contentPos = scrollToTop ? 0 : contentNode.scrollHeight,
			scrollPos = contentNode.scrollTop + contentPos,
			endChild = contentNode[scrollToTop ? 'firstChild' : 'lastChild'],
			hasPreload = endChild.className.indexOf('dgrid-preload') > -1,
			endTarget = hasPreload ? endChild[(scrollToTop ? 'next' : 'previous') + 'Sibling'] : endChild,
			handle;

		// Scroll explicitly rather than relying on native browser scrolling
		// (which might use smooth scrolling, which could incur extra renders for OnDemandList)
		event.preventDefault();
		this.scrollTo({
			y: scrollPos
		});

		if (hasPreload) {
			// Find the nearest dgrid-row to the relevant end of the grid
			while (endTarget && endTarget.className.indexOf('dgrid-row') < 0) {
				endTarget = endTarget[(scrollToTop ? 'next' : 'previous') + 'Sibling'];
			}
			// If none is found, there are no rows, and nothing to navigate
			if (!endTarget) {
				return;
			}
		}

		// Grid content may be lazy-loaded, so check if content needs to be
		// loaded first
		if (!hasPreload || endChild.offsetHeight < 1) {
			// End row is loaded; focus the first/last row/cell now
			if (cellNavigation) {
				// Preserve column that was currently focused
				endTarget = this.cell(endTarget, this.cell(event).column.id);
			}
			this._focusOnNode(endTarget, false, event);
		}
		else {
			// In IE < 9, the event member references will become invalid by the time
			// _focusOnNode is called, so make a (shallow) copy up-front
			if (!has('dom-addeventlistener')) {
				event = lang.mixin({}, event);
			}

			// If the topmost/bottommost row rendered doesn't reach the top/bottom of
			// the contentNode, we are using OnDemandList and need to wait for more
			// data to render, then focus the first/last row in the new content.
			handle = aspect.after(this, 'renderArray', function (rows) {
				var target = rows[scrollToTop ? 0 : rows.length - 1];
				if (cellNavigation) {
					// Preserve column that was currently focused
					target = this.cell(target, this.cell(event).column.id);
				}
				this._focusOnNode(target, false, event);
				handle.remove();
				return rows;
			});
		}
	};

	var moveFocusHome = Keyboard.moveFocusHome = function (event) {
		moveFocusEnd.call(this, event, true);
	};

	function preventDefault(event) {
		event.preventDefault();
	}

	Keyboard.defaultKeyMap = {
		32: preventDefault, // space
		33: moveFocusPageUp, // page up
		34: moveFocusPageDown, // page down
		35: moveFocusEnd, // end
		36: moveFocusHome, // home
		37: moveFocusLeft, // left
		38: moveFocusUp, // up
		39: moveFocusRight, // right
		40: moveFocusDown // down
	};

	// Header needs fewer default bindings (no vertical), so bind it separately
	Keyboard.defaultHeaderKeyMap = {
		32: preventDefault, // space
		35: moveHeaderFocusEnd, // end
		36: moveHeaderFocusHome, // home
		37: moveFocusLeft, // left
		39: moveFocusRight // right
	};

	return Keyboard;
});
