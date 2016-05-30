define([
	'dojo/_base/declare',
	'dojo/on',
	'dojo/has',
	'./util/misc',
	'xstyle/has-class',
	'put-selector/put',
	'dojo/_base/sniff',
	'xstyle/css!./css/dgrid.css'
], function (declare, listen, has, miscUtil, hasClass, put) {
	// Add user agent/feature CSS classes
	hasClass('mozilla', 'touch');

	// Add a feature test for pointer (only Dojo 1.10 has pointer-events and MSPointer tests)
	has.add('pointer', function (global) {
		return 'PointerEvent' in global ? 'pointer' :
			'MSPointerEvent' in global ? 'MSPointer' : false;
	});

	var oddClass = 'dgrid-row-odd',
		evenClass = 'dgrid-row-even',
		scrollbarWidth, scrollbarHeight;

	function byId(id) {
		return document.getElementById(id);
	}

	function cleanupTestElement(element) {
		element.className = '';
		if (element.parentNode) {
			document.body.removeChild(element);
		}
	}

	function getScrollbarSize(element, dimension) {
		// Used by has tests for scrollbar width/height
		put(document.body, element, '.dgrid-scrollbar-measure');
		var size = element['offset' + dimension] - element['client' + dimension];
		cleanupTestElement(element);
		return size;
	}
	has.add('dom-scrollbar-width', function (global, doc, element) {
		return getScrollbarSize(element, 'Width');
	});
	has.add('dom-scrollbar-height', function (global, doc, element) {
		return getScrollbarSize(element, 'Height');
	});

	has.add('dom-rtl-scrollbar-left', function (global, doc, element) {
		var div = put('div'),
			isLeft;

		put(document.body, element, '.dgrid-scrollbar-measure[dir=rtl]');
		put(element, div);

		// position: absolute makes modern IE and Edge always report child's offsetLeft as 0,
		// but other browsers factor in the position of the scrollbar if it is to the left.
		// All versions of IE and Edge are known to move the scrollbar to the left side for rtl.
		isLeft = !!has('ie') || !!has('trident') || /\bEdge\//.test(navigator.userAgent) ||
			div.offsetLeft >= has('dom-scrollbar-width');
		cleanupTestElement(element);
		put(div, '!');
		element.removeAttribute('dir');
		return isLeft;
	});

	// var and function for autogenerating ID when one isn't provided
	var autoId = 0;
	function generateId() {
		return List.autoIdPrefix + autoId++;
	}

	// common functions for class and className setters/getters
	// (these are run in instance context)
	var spaceRx = / +/g;
	function setClass(cls) {
		// Format input appropriately for use with put...
		var putClass = cls ? '.' + cls.replace(spaceRx, '.') : '';

		// Remove any old classes, and add new ones.
		if (this._class) {
			putClass = '!' + this._class.replace(spaceRx, '!') + putClass;
		}
		put(this.domNode, putClass);

		// Store for later retrieval/removal.
		this._class = cls;
	}
	function getClass() {
		return this._class;
	}

	// window resize event handler, run in context of List instance
	var winResizeHandler = function () {
		if (this._started) {
			this.resize();
		}
	};

	var List = declare(null, {
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

		// addUiClasses: Boolean
		//		Whether to add jQuery UI classes to various elements in dgrid's DOM.
		addUiClasses: true,

		// highlightDuration: Integer
		//		The amount of time (in milliseconds) that a row should remain
		//		highlighted after it has been updated.
		highlightDuration: 250,

		postscript: function (params, srcNodeRef) {
			// perform setup and invoke create in postScript to allow descendants to
			// perform logic before create/postCreate happen (a la dijit/_WidgetBase)
			var grid = this;

			(this._Row = function (id, object, element) {
				this.id = id;
				this.data = object;
				this.element = element;
			}).prototype.remove = function () {
				grid.removeRow(this.element);
			};

			if (srcNodeRef) {
				// normalize srcNodeRef and store on instance during create process.
				// Doing this in postscript is a bit earlier than dijit would do it,
				// but allows subclasses to access it pre-normalized during create.
				this.srcNodeRef = srcNodeRef =
					srcNodeRef.nodeType ? srcNodeRef : byId(srcNodeRef);
			}
			this.create(params, srcNodeRef);
		},
		listType: 'list',

		create: function (params, srcNodeRef) {
			var domNode = this.domNode = srcNodeRef || put('div'),
				cls;

			if (params) {
				this.params = params;
				declare.safeMixin(this, params);

				// Check for initial class or className in params or on domNode
				cls = params['class'] || params.className || domNode.className;
			}

			// ensure arrays and hashes are initialized
			this.sort = this.sort || [];
			this._listeners = [];
			this._rowIdToObject = {};

			this.postMixInProperties && this.postMixInProperties();

			// Apply id to widget and domNode,
			// from incoming node, widget params, or autogenerated.
			this.id = domNode.id = domNode.id || this.id || generateId();

			// Perform initial rendering, and apply classes if any were specified.
			this.buildRendering();
			if (cls) {
				setClass.call(this, cls);
			}

			this.postCreate();

			// remove srcNodeRef instance property post-create
			delete this.srcNodeRef;
			// to preserve "it just works" behavior, call startup if we're visible
			if (this.domNode.offsetHeight) {
				this.startup();
			}
		},
		buildRendering: function () {
			var domNode = this.domNode,
				addUiClasses = this.addUiClasses,
				self = this,
				headerNode, bodyNode, footerNode, isRTL;

			// Detect RTL on html/body nodes; taken from dojo/dom-geometry
			isRTL = this.isRTL = (document.body.dir || document.documentElement.dir ||
				document.body.style.direction).toLowerCase() === 'rtl';

			// Clear out className (any pre-applied classes will be re-applied via the
			// class / className setter), then apply standard classes/attributes
			domNode.className = '';

			put(domNode, '[role=grid].dgrid.dgrid-' + this.listType +
				(addUiClasses ? '.ui-widget' : ''));

			// Place header node (initially hidden if showHeader is false).
			headerNode = this.headerNode = put(domNode,
				'div.dgrid-header.dgrid-header-row' +
				(addUiClasses ? '.ui-widget-header' : '') +
				(this.showHeader ? '' : '.dgrid-header-hidden'));
			bodyNode = this.bodyNode = put(domNode, 'div.dgrid-scroller');

			// Firefox 4+ adds overflow: auto elements to the tab index by default;
			// force them to not be tabbable, but restrict this to Firefox,
			// since it breaks accessibility support in other browsers
			if (has('ff')) {
				bodyNode.tabIndex = -1;
			}

			this.headerScrollNode = put(domNode, 'div.dgrid-header.dgrid-header-scroll.dgrid-scrollbar-width' +
				(addUiClasses ? '.ui-widget-header' : ''));

			// Place footer node (initially hidden if showFooter is false).
			footerNode = this.footerNode = put('div.dgrid-footer' +
				(this.showFooter ? '' : '.dgrid-footer-hidden'));
			put(domNode, footerNode);

			if (isRTL) {
				domNode.className += ' dgrid-rtl' +
					(has('dom-rtl-scrollbar-left') ? ' dgrid-rtl-swap' : '');
			}

			listen(bodyNode, 'scroll', function (event) {
				if (self.showHeader) {
					// keep the header aligned with the body
					headerNode.scrollLeft = event.scrollLeft || bodyNode.scrollLeft;
				}
				// re-fire, since browsers are not consistent about propagation here
				event.stopPropagation();
				listen.emit(domNode, 'scroll', {scrollTarget: bodyNode});
			});
			this.configStructure();
			this.renderHeader();

			this.contentNode = this.touchNode = put(this.bodyNode,
				'div.dgrid-content' + (addUiClasses ? '.ui-widget-content' : ''));
			// add window resize handler, with reference for later removal if needed
			this._listeners.push(this._resizeHandle = listen(window, 'resize',
				miscUtil.throttleDelayed(winResizeHandler, this)));
		},

		postCreate: function () {
		},

		startup: function () {
			// summary:
			//		Called automatically after postCreate if the component is already
			//		visible; otherwise, should be called manually once placed.

			if (this._started) {
				return;
			}
			this.inherited(arguments);
			this._started = true;
			this.resize();
			// apply sort (and refresh) now that we're ready to render
			this.set('sort', this.sort);
		},

		configStructure: function () {
			// does nothing in List, this is more of a hook for the Grid
		},
		resize: function () {
			var bodyNode = this.bodyNode,
				headerNode = this.headerNode,
				footerNode = this.footerNode,
				headerHeight = headerNode.offsetHeight,
				footerHeight = this.showFooter ? footerNode.offsetHeight : 0;

			this.headerScrollNode.style.height = bodyNode.style.marginTop = headerHeight + 'px';
			bodyNode.style.marginBottom = footerHeight + 'px';

			if (!scrollbarWidth) {
				// Measure the browser's scrollbar width using a DIV we'll delete right away
				scrollbarWidth = has('dom-scrollbar-width');
				scrollbarHeight = has('dom-scrollbar-height');

				// Avoid issues with certain widgets inside in IE7, and
				// ColumnSet scroll issues with all supported IE versions
				if (has('ie')) {
					scrollbarWidth++;
					scrollbarHeight++;
				}

				// add rules that can be used where scrollbar width/height is needed
				miscUtil.addCssRule('.dgrid-scrollbar-width', 'width: ' + scrollbarWidth + 'px');
				miscUtil.addCssRule('.dgrid-scrollbar-height', 'height: ' + scrollbarHeight + 'px');

				if (scrollbarWidth !== 17) {
					// for modern browsers, we can perform a one-time operation which adds
					// a rule to account for scrollbar width in all grid headers.
					miscUtil.addCssRule('.dgrid-header-row', 'right: ' + scrollbarWidth + 'px');
					// add another for RTL grids
					miscUtil.addCssRule('.dgrid-rtl-swap .dgrid-header-row', 'left: ' + scrollbarWidth + 'px');
				}
			}
		},

		addCssRule: function (selector, css) {
			// summary:
			//		Version of util/misc.addCssRule which tracks added rules and removes
			//		them when the List is destroyed.

			var rule = miscUtil.addCssRule(selector, css);
			if (this.cleanAddedRules) {
				// Although this isn't a listener, it shares the same remove contract
				this._listeners.push(rule);
			}
			return rule;
		},

		on: function (eventType, listener) {
			// delegate events to the domNode
			var signal = listen(this.domNode, eventType, listener);
			if (!has('dom-addeventlistener')) {
				this._listeners.push(signal);
			}
			return signal;
		},

		cleanup: function () {
			// summary:
			//		Clears out all rows currently in the list.

			var i;
			for (i in this._rowIdToObject) {
				if (this._rowIdToObject[i] !== this.columns) {
					var rowElement = byId(i);
					if (rowElement) {
						this.removeRow(rowElement, true);
					}
				}
			}
		},
		destroy: function () {
			// summary:
			//		Destroys this grid

			// Remove any event listeners and other such removables
			if (this._listeners) { // Guard against accidental subsequent calls to destroy
				for (var i = this._listeners.length; i--;) {
					this._listeners[i].remove();
				}
				this._listeners = null;
			}

			this._started = false;
			this.cleanup();
			// destroy DOM
			put(this.domNode, '!');
		},
		refresh: function () {
			// summary:
			//		refreshes the contents of the grid
			this.cleanup();
			this._rowIdToObject = {};
			this._autoRowId = 0;

			// make sure all the content has been removed so it can be recreated
			this.contentNode.innerHTML = '';
			// Ensure scroll position always resets (especially for TouchScroll).
			this.scrollTo({ x: 0, y: 0 });
		},

		highlightRow: function (rowElement, delay) {
			// summary:
			//		Highlights a row.  Used when updating rows due to store
			//		notifications, but potentially also useful in other cases.
			// rowElement: Object
			//		Row element (or object returned from the row method) to
			//		highlight.
			// delay: Number
			//		Number of milliseconds between adding and removing the
			//		ui-state-highlight class.

			rowElement = rowElement.element || rowElement;
			put(rowElement, '.dgrid-highlight' +
				(this.addUiClasses ? '.ui-state-highlight' : ''));
			setTimeout(function () {
				put(rowElement, '!dgrid-highlight!ui-state-highlight');
			}, delay || this.highlightDuration);
		},

		adjustRowIndices: function (firstRow) {
			// this traverses through rows to maintain odd/even classes on the rows when indexes shift;
			var next = firstRow;
			var rowIndex = next.rowIndex;
			if (rowIndex > -1) { // make sure we have a real number in case this is called on a non-row
				do {
					// Skip non-numeric, non-rows
					if (next.rowIndex > -1) {
						if (this.maintainOddEven) {
							if ((next.className + ' ').indexOf('dgrid-row ') > -1) {
								put(next, '.' + (rowIndex % 2 === 1 ? oddClass : evenClass) + '!' +
									(rowIndex % 2 === 0 ? oddClass : evenClass));
							}
						}
						next.rowIndex = rowIndex++;
					}
				} while ((next = next.nextSibling) && next.rowIndex !== rowIndex);
			}
		},
		renderArray: function (results, beforeNode, options) {
			// summary:
			//		Renders an array of objects as rows, before the given node.

			options = options || {};
			var self = this,
				start = options.start || 0,
				rowsFragment = document.createDocumentFragment(),
				rows = [],
				container,
				i = 0,
				len = results.length;

			if (!beforeNode) {
				this._lastCollection = results;
			}

			// Insert a row for each item into the document fragment
			while (i < len) {
				rows[i] = this.insertRow(results[i], rowsFragment, null, start++, options);
				i++;
			}

			// Insert the document fragment into the appropriate position
			container = beforeNode ? beforeNode.parentNode : self.contentNode;
			if (container && container.parentNode &&
					(container !== self.contentNode || len)) {
				container.insertBefore(rowsFragment, beforeNode || null);
				if (len) {
					self.adjustRowIndices(rows[len - 1]);
				}
			}

			return rows;
		},

		renderHeader: function () {
			// no-op in a plain list
		},

		_autoRowId: 0,
		insertRow: function (object, parent, beforeNode, i, options) {
			// summary:
			//		Creates a single row in the grid.

			// Include parentId within row identifier if one was specified in options.
			// (This is used by tree to allow the same object to appear under
			// multiple parents.)
			var id = this.id + '-row-' + ((this.collection && this.collection.getIdentity) ?
					this.collection.getIdentity(object) : this._autoRowId++),
				row = byId(id),
				previousRow = row && row.previousSibling;

			if (row) {
				// If it existed elsewhere in the DOM, we will remove it, so we can recreate it
				if (row === beforeNode) {
					beforeNode = (beforeNode.connected || beforeNode).nextSibling;
				}
				this.removeRow(row, false, options);
			}
			row = this.renderRow(object, options);
			row.className = (row.className || '') + ' dgrid-row ' +
				(i % 2 === 1 ? oddClass : evenClass) +
				(this.addUiClasses ? ' ui-state-default' : '');
			// Get the row id for easy retrieval
			this._rowIdToObject[row.id = id] = object;
			parent.insertBefore(row, beforeNode || null);

			row.rowIndex = i;
			if (previousRow && previousRow.rowIndex !== (row.rowIndex - 1)) {
				// In this case, we are pulling the row from another location in the grid,
				// and we need to readjust the rowIndices from the point it was removed
				this.adjustRowIndices(previousRow);
			}
			return row;
		},
		renderRow: function (value) {
			// summary:
			//		Responsible for returning the DOM for a single row in the grid.
			// value: Mixed
			//		Value to render
			// options: Object?
			//		Optional object with additional options

			return put('div', '' + value);
		},
		removeRow: function (rowElement, preserveDom) {
			// summary:
			//		Simply deletes the node in a plain List.
			//		Column plugins may aspect this to implement their own cleanup routines.
			// rowElement: Object|DOMNode
			//		Object or element representing the row to be removed.
			// preserveDom: Boolean?
			//		If true, the row element will not be removed from the DOM; this can
			//		be used by extensions/plugins in cases where the DOM will be
			//		massively cleaned up at a later point in time.
			// options: Object?
			//		May be specified with a `rows` property for the purpose of
			//		cleaning up collection tracking (used by `_StoreMixin`).

			rowElement = rowElement.element || rowElement;
			delete this._rowIdToObject[rowElement.id];
			if (!preserveDom) {
				put(rowElement, '!');
			}
		},

		row: function (target) {
			// summary:
			//		Get the row object by id, object, node, or event
			var id;

			if (target instanceof this._Row) {
				return target; // No-op; already a row
			}

			if (target.target && target.target.nodeType) {
				// Event
				target = target.target;
			}
			if (target.nodeType) {
				// Row element, or child of a row element
				var object;
				do {
					var rowId = target.id;
					if ((object = this._rowIdToObject[rowId])) {
						return new this._Row(rowId.substring(this.id.length + 5), object, target);
					}
					target = target.parentNode;
				}while (target && target !== this.domNode);
				return;
			}

			if (typeof target === 'object') {
				// Assume target represents a collection item
				id = this.collection.getIdentity(target);
			}
			else {
				// Assume target is a row ID
				id = target;
				target = this._rowIdToObject[this.id + '-row-' + id];
			}
			return new this._Row(id, target, byId(this.id + '-row-' + id));
		},
		cell: function (target) {
			// this doesn't do much in a plain list
			return {
				row: this.row(target)
			};
		},

		_move: function (item, steps, targetClass, visible) {
			var nextSibling, current, element;
			// Start at the element indicated by the provided row or cell object.
			element = current = item.element;
			steps = steps || 1;

			do {
				// Outer loop: move in the appropriate direction.
				if ((nextSibling = current[steps < 0 ? 'previousSibling' : 'nextSibling'])) {
					do {
						// Inner loop: advance, and dig into children if applicable.
						current = nextSibling;
						if (current && (current.className + ' ').indexOf(targetClass + ' ') > -1) {
							// Element with the appropriate class name; count step, stop digging.
							element = current;
							steps += steps < 0 ? 1 : -1;
							break;
						}
						// If the next sibling isn't a match, drill down to search, unless
						// visible is true and children are hidden.
					} while ((nextSibling = (!visible || !current.hidden) &&
						current[steps < 0 ? 'lastChild' : 'firstChild']));
				}
				else {
					current = current.parentNode;
					if (!current || current === this.bodyNode || current === this.headerNode) {
						// Break out if we step out of the navigation area entirely.
						break;
					}
				}
			}while (steps);
			// Return the final element we arrived at, which might still be the
			// starting element if we couldn't navigate further in that direction.
			return element;
		},

		up: function (row, steps, visible) {
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
			if (!row.element) {
				row = this.row(row);
			}
			return this.row(this._move(row, -(steps || 1), 'dgrid-row', visible));
		},
		down: function (row, steps, visible) {
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
			if (!row.element) {
				row = this.row(row);
			}
			return this.row(this._move(row, steps || 1, 'dgrid-row', visible));
		},

		scrollTo: function (options) {
			if (typeof options.x !== 'undefined') {
				this.bodyNode.scrollLeft = options.x;
			}
			if (typeof options.y !== 'undefined') {
				this.bodyNode.scrollTop = options.y;
			}
		},

		getScrollPosition: function () {
			return {
				x: this.bodyNode.scrollLeft,
				y: this.bodyNode.scrollTop
			};
		},

		get: function (/*String*/ name /*, ... */) {
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

			var fn = '_get' + name.charAt(0).toUpperCase() + name.slice(1);

			if (typeof this[fn] === 'function') {
				return this[fn].apply(this, [].slice.call(arguments, 1));
			}

			// Alert users that try to use Dijit-style getter/setters so they don’t get confused
			// if they try to use them and it does not work
			if (!has('dojo-built') && typeof this[fn + 'Attr'] === 'function') {
				console.warn('dgrid: Use ' + fn + ' instead of ' + fn + 'Attr for getting ' + name);
			}

			return this[name];
		},

		set: function (/*String*/ name, /*Object*/ value /*, ... */) {
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

			if (typeof name === 'object') {
				for (var k in name) {
					this.set(k, name[k]);
				}
			}
			else {
				var fn = '_set' + name.charAt(0).toUpperCase() + name.slice(1);

				if (typeof this[fn] === 'function') {
					this[fn].apply(this, [].slice.call(arguments, 1));
				}
				else {
					// Alert users that try to use Dijit-style getter/setters so they don’t get confused
					// if they try to use them and it does not work
					if (!has('dojo-built') && typeof this[fn + 'Attr'] === 'function') {
						console.warn('dgrid: Use ' + fn + ' instead of ' + fn + 'Attr for setting ' + name);
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

		_setSort: function (property, descending) {
			// summary:
			//		Sort the content
			// property: String|Array
			//		String specifying field to sort by, or actual array of objects
			//		with property and descending properties
			// descending: boolean
			//		In the case where property is a string, this argument
			//		specifies whether to sort ascending (false) or descending (true)

			this.sort = typeof property !== 'string' ? property :
				[{property: property, descending: descending}];

			this._applySort();
		},

		_applySort: function () {
			// summary:
			//		Applies the current sort
			// description:
			//		This is an extension point to allow specializations to apply the sort differently

			this.refresh();

			if (this._lastCollection) {
				var sort = this.sort;
				if (sort && sort.length > 0) {
					var property = sort[0].property,
						descending = !!sort[0].descending;
					this._lastCollection.sort(function (a, b) {
						var aVal = a[property], bVal = b[property];
						// fall back undefined values to "" for more consistent behavior
						if (aVal === undefined) {
							aVal = '';
						}
						if (bVal === undefined) {
							bVal = '';
						}
						return aVal === bVal ? 0 : (aVal > bVal !== descending ? 1 : -1);
					});
				}
				this.renderArray(this._lastCollection);
			}
		},

		_setShowHeader: function (show) {
			// this is in List rather than just in Grid, primarily for two reasons:
			// (1) just in case someone *does* want to show a header in a List
			// (2) helps address IE < 8 header display issue in List

			var headerNode = this.headerNode;

			this.showHeader = show;

			// add/remove class which has styles for "hiding" header
			put(headerNode, (show ? '!' : '.') + 'dgrid-header-hidden');

			this.renderHeader();
			this.resize(); // resize to account for (dis)appearance of header

			if (show) {
				// Update scroll position of header to make sure it's in sync.
				headerNode.scrollLeft = this.getScrollPosition().x;
			}
		},

		_setShowFooter: function (show) {
			this.showFooter = show;

			// add/remove class which has styles for hiding footer
			put(this.footerNode, (show ? '!' : '.') + 'dgrid-footer-hidden');

			this.resize(); // to account for (dis)appearance of footer
		}
	});

	List.autoIdPrefix = 'dgrid_';

	return List;
});
