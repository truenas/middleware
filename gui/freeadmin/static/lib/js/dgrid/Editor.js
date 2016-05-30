define([
	'dojo/_base/declare',
	'dojo/_base/lang',
	'dojo/Deferred',
	'dojo/on',
	'dojo/has',
	'dojo/query',
	'./Grid',
	'put-selector/put',
	'dojo/_base/sniff'
], function (declare, lang, Deferred, on, has, query, Grid, put) {

	return declare(null, {
		constructor: function () {
			this._editorInstances = {};
			// Tracks shared editor dismissal listeners, and editor click/change listeners for old IE
			this._editorColumnListeners = [];
			// Tracks always-on editor listeners for old IE, or listeners for triggering shared editors
			this._editorCellListeners = {};
			this._editorsPendingStartup = [];
		},

		postCreate: function () {
			var self = this;

			this.inherited(arguments);

			this.on('.dgrid-input:focusin', function () {
				self._focusedEditorCell = self.cell(this);
			});
			this._editorFocusoutHandle = on.pausable(this.domNode, '.dgrid-input:focusout', function () {
				self._focusedEditorCell = null;
			});
			this._listeners.push(this._editorFocusoutHandle);
		},

		insertRow: function () {
			this._editorRowListeners = {};
			var rowElement = this.inherited(arguments);
			var row = this.row(rowElement);
			var rowListeners = this._editorCellListeners[rowElement.id] =
				this._editorCellListeners[rowElement.id] || {};

			for (var key in this._editorRowListeners) {
				rowListeners[key] = this._editorRowListeners[key];
			}
			// Null this out so that _createEditor can tell whether the editor being created is
			// an individual cell editor at insertion time
			this._editorRowListeners = null;

			var previouslyFocusedCell = this._previouslyFocusedEditorCell;

			if (previouslyFocusedCell && previouslyFocusedCell.row.id === row.id) {
				this.edit(this.cell(row, previouslyFocusedCell.column.id));
			}
			return rowElement;
		},

		refresh: function () {
			for (var id in this._editorInstances) {
				var editorInstanceDomNode = this._editorInstances[id].domNode;
				if (editorInstanceDomNode && editorInstanceDomNode.parentNode) {
					// Remove any editor widgets from the DOM before List destroys it, to avoid issues in IE (#1100)
					editorInstanceDomNode.parentNode.removeChild(editorInstanceDomNode);
				}
			}

			this.inherited(arguments);
		},

		removeRow: function (rowElement) {
			var self = this;
			var focusedCell = this._focusedEditorCell;

			if (focusedCell && focusedCell.row.id === this.row(rowElement).id) {
				this._previouslyFocusedEditorCell = focusedCell;
				// Pause the focusout handler until after this row has had
				// time to re-render, if this removal is part of an update.
				// A setTimeout is used here instead of resuming in insertRow,
				// since if a row were actually removed (not updated) while
				// editing, the handler would not be properly hooked up again
				// for future occurrences.
				this._editorFocusoutHandle.pause();
				setTimeout(function () {
					self._editorFocusoutHandle.resume();
					self._previouslyFocusedEditorCell = null;
				}, 0);
			}

			if (this._editorCellListeners[rowElement.id]) {
				for (var columnId in this._editorCellListeners[rowElement.id]) {
					this._editorCellListeners[rowElement.id][columnId].remove();
				}
				delete this._editorCellListeners[rowElement.id];
			}

			for (var i = this._alwaysOnWidgetColumns.length; i--;) {
				// Destroy always-on editor widgets during the row removal operation,
				// but don't trip over loading nodes from incomplete requests
				var cellElement = this.cell(rowElement, this._alwaysOnWidgetColumns[i].id).element,
					widget = cellElement && (cellElement.contents || cellElement).widget;
				if (widget) {
					this._editorFocusoutHandle.pause();
					widget.destroyRecursive();
				}
			}

			return this.inherited(arguments);
		},

		renderArray: function () {
			var rows = this.inherited(arguments);
			if (rows.length) {
				// Finish processing any pending editors that are now displayed
				this._startupPendingEditors();
			}
			else {
				this._editorsPendingStartup = [];
			}
			return rows;
		},

		_onNotification: function () {
			this.inherited(arguments);
			this._startupPendingEditors();
		},

		_destroyColumns: function () {
			this._editorStructureCleanup();
			this.inherited(arguments);
		},

		_editorStructureCleanup: function () {
			var editorInstances = this._editorInstances;
			var listeners = this._editorColumnListeners;

			if (this._editTimer) {
				clearTimeout(this._editTimer);
			}
			// Do any clean up of previous column structure.
			for (var columnId in editorInstances) {
				var editor = editorInstances[columnId];
				if (editor.domNode) {
					// The editor is a widget
					editor.destroyRecursive();
				}
			}
			this._editorInstances = {};

			for (var i = listeners.length; i--;) {
				listeners[i].remove();
			}

			for (var rowId in this._editorCellListeners) {
				for (columnId in this._editorCellListeners[rowId]) {
					this._editorCellListeners[rowId][columnId].remove();
				}
			}

			for (i = 0; i < this._editorColumnListeners.length; i++) {
				this._editorColumnListeners[i].remove();
			}

			this._editorCellListeners = {};
			this._editorColumnListeners = [];
			this._editorsPendingStartup = [];
		},

		_configColumns: function () {
			var columnArray = this.inherited(arguments);
			this._alwaysOnWidgetColumns = [];
			for (var i = 0, l = columnArray.length; i < l; i++) {
				if (columnArray[i].editor) {
					this._configureEditorColumn(columnArray[i]);
				}
			}
			return columnArray;
		},

		_configureEditorColumn: function (column) {
			// summary:
			//		Adds editing capability to a column's cells.

			var editor = column.editor;
			var self = this;

			var originalRenderCell = column.renderCell || this._defaultRenderCell;
			var editOn = column.editOn;
			var isWidget = typeof editor !== 'string';

			if (editOn) {
				// Create one shared widget/input to be swapped into the active cell.
				this._editorInstances[column.id] = this._createSharedEditor(column, originalRenderCell);
			}
			else if (isWidget) {
				// Append to array iterated in removeRow
				this._alwaysOnWidgetColumns.push(column);
			}

			column.renderCell = editOn ? function (object, value, cell, options) {
				// TODO: Consider using event delegation
				// (Would require using dgrid's focus events for activating on focus,
				// which we already advocate in docs for optimal use)

				if (!options || !options.alreadyHooked) {
					var listener = on(cell, editOn, function () {
						self._activeOptions = options;
						self.edit(this);
					});
					if (self._editorRowListeners) {
						self._editorRowListeners[column.id] = listener;
					}
				}

				// initially render content in non-edit mode
				return originalRenderCell.call(column, object, value, cell, options);

			} : function (object, value, cell, options) {
				// always-on: create editor immediately upon rendering each cell
				if (!column.canEdit || column.canEdit(object, value)) {
					var cmp = self._createEditor(column);
					self._showEditor(cmp, column, cell, value);
					// Maintain reference for later use.
					cell[isWidget ? 'widget' : 'input'] = cmp;
				}
				else {
					return originalRenderCell.call(column, object, value, cell, options);
				}
			};
		},

		edit: function (cell) {
			// summary:
			//		Shows/focuses the editor for a given grid cell.
			// cell: Object
			//		Cell (or something resolvable by grid.cell) to activate editor on.
			// returns:
			//		If the cell is editable, returns a promise resolving to the editor
			//		input/widget when the cell editor is focused.
			//		If the cell is not editable, returns null.

			var self = this;
			var column;
			var cellElement;
			var dirty;
			var field;
			var value;
			var cmp;
			var dfd;

			function showEditor(dfd) {
				self._activeCell = cellElement;
				self._showEditor(cmp, column, cellElement, value);

				// focus / blur-handler-resume logic is surrounded in a setTimeout
				// to play nice with Keyboard's dgrid-cellfocusin as an editOn event
				self._editTimer = setTimeout(function () {
					// focus the newly-placed control (supported by form widgets and HTML inputs)
					if (cmp.focus) {
						cmp.focus();
					}
					// resume blur handler once editor is focused
					if (column._editorBlurHandle) {
						column._editorBlurHandle.resume();
					}
					self._editTimer = null;
					dfd.resolve(cmp);
				}, 0);
			}

			if (!cell.column) {
				cell = this.cell(cell);
			}
			if (!cell || !cell.element) {
				return null;
			}

			column = cell.column;
			field = column.field;
			cellElement = cell.element.contents || cell.element;

			if ((cmp = this._editorInstances[column.id])) {
				// Shared editor (editOn used)
				if (this._activeCell !== cellElement) {
					// Get the cell value
					var row = cell.row;
					dirty = this.dirty && this.dirty[row.id];
					value = (dirty && field in dirty) ? dirty[field] :
						column.get ? column.get(row.data) : row.data[field];
					// Check to see if the cell can be edited
					if (!column.canEdit || column.canEdit(cell.row.data, value)) {
						dfd = new Deferred();

						// In some browsers, moving a DOM node causes a blur event to fire which in this case,
						// is a bad time for the blur handler to run.  Blur the input node first.
						var node = cmp.domNode || cmp;
						if (node.offsetWidth) {
							// The editor is visible.  Blur it.
							node.blur();
							// In IE, the blur does not complete immediately.
							// Push showing of the editor to the next turn.
							// (dfd will be resolved within showEditor)
							setTimeout(function () {
								showEditor(dfd);
							}, 0);
						} else {
							showEditor(dfd);
						}

						return dfd.promise;
					}
				}
			}
			else if (column.editor) {
				// editor but not shared; always-on
				cmp = cellElement.widget || cellElement.input;
				if (cmp) {
					dfd = new Deferred();
					if (cmp.focus) {
						cmp.focus();
					}
					dfd.resolve(cmp);
					return dfd.promise;
				}
			}
			return null;
		},

		_showEditor: function (cmp, column, cellElement, value) {
			// Places a shared editor into the newly-active cell in the column.
			// Also called when rendering an editor in an "always-on" editor column.

			var isWidget = cmp.domNode;
			// for regular inputs, we can update the value before even showing it
			if (!isWidget) {
				this._updateInputValue(cmp, value);
			}

			cellElement.innerHTML = '';
			put(cellElement, '.dgrid-cell-editing');
			put(cellElement, cmp.domNode || cmp);

			// If a shared editor is a validation widget, reset it to clear validation state
			// (The value will be preserved since it is explicitly set in _startupEditor)
			if (isWidget && column.editOn && cmp.validate && cmp.reset) {
				cmp.reset();
			}

			if (isWidget && !column.editOn) {
				// Queue arguments to be run once editor is in DOM
				this._editorsPendingStartup.push([cmp, column, cellElement, value]);
			}
			else {
				this._startupEditor(cmp, column, cellElement, value);
			}
		},

		_startupEditor: function (cmp, column, cellElement, value) {
			// summary:
			//		Handles editor widget startup logic and updates the editor's value.

			if (cmp.domNode) {
				// For widgets, ensure startup is called before setting value, to maximize compatibility
				// with flaky widgets like dijit/form/Select.
				if (!cmp._started) {
					cmp.startup();
				}

				// Set value, but ensure it isn't processed as a user-generated change.
				// (Clear flag on a timeout to wait for delayed onChange to fire first)
				cmp._dgridIgnoreChange = true;
				cmp.set('value', value);
				setTimeout(function () {
					cmp._dgridIgnoreChange = false;
				}, 0);
			}

			// track previous value for short-circuiting or in case we need to revert
			cmp._dgridLastValue = value;
			// if this is an editor with editOn, also update _activeValue
			// (_activeOptions will have been updated previously)
			if (this._activeCell) {
				this._activeValue = value;
				// emit an event immediately prior to placing a shared editor
				on.emit(cellElement, 'dgrid-editor-show', {
					grid: this,
					cell: this.cell(cellElement),
					column: column,
					editor: cmp,
					bubbles: true,
					cancelable: false
				});
			}
		},

		_startupPendingEditors: function () {
			var args = this._editorsPendingStartup;
			for (var i = args.length; i--;) {
				this._startupEditor.apply(this, args[i]);
			}
			this._editorsPendingStartup = [];
		},

		_handleEditorChange: function (evt, column) {
			var target = evt.target;
			if ('_dgridLastValue' in target && target.className.indexOf('dgrid-input') > -1) {
				this._updatePropertyFromEditor(column || this.cell(target).column, target, evt);
			}
		},

		_createEditor: function (column) {
			// Creates an editor instance based on column definition properties,
			// and hooks up events.
			var editor = column.editor,
				editOn = column.editOn,
				self = this,
				Widget = typeof editor !== 'string' && editor,
				args, cmp, node, putstr;

			args = column.editorArgs || {};
			if (typeof args === 'function') {
				args = args.call(this, column);
			}

			if (Widget) {
				cmp = new Widget(args);
				node = cmp.focusNode || cmp.domNode;

				// Add dgrid-input to className to make consistent with HTML inputs.
				node.className += ' dgrid-input';

				// For editOn editors, connect to onBlur rather than onChange, since
				// the latter is delayed by setTimeouts in Dijit and will fire too late.
				cmp.on(editOn ? 'blur' : 'change', function () {
					if (!cmp._dgridIgnoreChange) {
						self._updatePropertyFromEditor(column, this, {type: 'widget'});
					}
				});
			}
			else {
				// considerations for standard HTML form elements
				if (!this._hasInputListener) {
					// register one listener at the top level that receives events delegated
					this._hasInputListener = true;
					this.on('change', function (evt) {
						self._handleEditorChange(evt);
					});
					// also register a focus listener
				}

				putstr = editor === 'textarea' ? 'textarea' :
					'input[type=' + editor + ']';
				cmp = node = put(putstr + '.dgrid-input', lang.mixin({
					name: column.field,
					tabIndex: isNaN(column.tabIndex) ? -1 : column.tabIndex
				}, args));

				if (has('ie') < 9) {
					// IE<9 doesn't fire change events for all the right things,
					// and it doesn't bubble.
					var listener;
					if (editor === 'radio' || editor === 'checkbox') {
						// listen for clicks since IE doesn't fire change events properly for checks/radios
						listener = on(cmp, 'click', function (evt) {
							self._handleEditorChange(evt, column);
						});
					}
					else {
						listener = on(cmp, 'change', function (evt) {
							self._handleEditorChange(evt, column);
						});
					}

					if (editOn) {
						// Shared editor handlers are maintained in _editorColumnListeners, since they're not per-row
						this._editorColumnListeners.push(listener);
					}
					else if (this._editorRowListeners) {
						this._editorRowListeners[column.id] = listener;
					}
				}
			}

			if (column.autoSelect) {
				var selectNode = cmp.focusNode || cmp;
				if (selectNode.select) {
					on(selectNode, 'focus', function () {
						// setTimeout is needed for always-on editors on WebKit,
						// otherwise selection is reset immediately afterwards
						setTimeout(function () {
							selectNode.select();
						}, 0);
					});
				}
			}

			return cmp;
		},

		_createSharedEditor: function (column) {
			// Creates an editor instance with additional considerations for
			// shared usage across an entire column (for columns with editOn specified).

			var cmp = this._createEditor(column),
				self = this,
				isWidget = cmp.domNode,
				node = cmp.domNode || cmp,
				focusNode = cmp.focusNode || node,
				reset = isWidget ?
					function () {
						cmp.set('value', cmp._dgridLastValue);
					} :
					function () {
						self._updateInputValue(cmp, cmp._dgridLastValue);
						// Update property again in case we need to revert a previous change
						self._updatePropertyFromEditor(column, cmp);
					};

			function blur() {
				var element = self._activeCell;
				focusNode.blur();

				if (typeof self.focus === 'function') {
					// Dijit form widgets don't end up dismissed until the next turn,
					// so wait before calling focus (otherwise Keyboard will focus the
					// input again).  IE<9 needs to wait longer, otherwise the cell loses
					// focus after we've set it.
					setTimeout(function () {
						self.focus(element);
					}, isWidget && has('ie') < 9 ? 15 : 0);
				}
			}

			function onblur() {
				var parentNode = node.parentNode,
					i = parentNode.children.length - 1,
					options = { alreadyHooked: true },
					cell = self.cell(node);

				// emit an event immediately prior to removing an editOn editor
				on.emit(cell.element, 'dgrid-editor-hide', {
					grid: self,
					cell: cell,
					column: column,
					editor: cmp,
					bubbles: true,
					cancelable: false
				});
				column._editorBlurHandle.pause();
				// Remove the editor from the cell, to be reused later.
				parentNode.removeChild(node);

				if (cell.row) {
					// If the row is still present (i.e. we didn't blur due to removal),
					// clear out the rest of the cell's contents, then re-render with new value.
					put(cell.element, '!dgrid-cell-editing');
					while (i--) {
						put(parentNode.firstChild, '!');
					}
					Grid.appendIfNode(parentNode, column.renderCell(cell.row.data, self._activeValue, parentNode,
						self._activeOptions ? lang.delegate(options, self._activeOptions) : options));
				}

				// Reset state now that editor is deactivated;
				// reset _focusedEditorCell as well since some browsers will not
				// trigger the focusout event handler in this case
				self._focusedEditorCell = self._activeCell = self._activeValue = self._activeOptions = null;
			}

			function dismissOnKey(evt) {
				// Contains logic for reacting to enter/escape keypresses to save/cancel edits.
				// Calls `focusNode.blur()` in cases where field should be dismissed.
				var key = evt.keyCode || evt.which;

				if (key === 27) {
					// Escape: revert + dismiss
					reset();
					self._activeValue = cmp._dgridLastValue;
					blur();
				}
				else if (key === 13 && column.dismissOnEnter !== false) {
					// Enter: dismiss
					blur();
				}
			}

			// hook up enter/esc key handling
			this._editorColumnListeners.push(on(focusNode, 'keydown', dismissOnKey));

			// hook up blur handler, but don't activate until widget is activated
			(column._editorBlurHandle = on.pausable(cmp, 'blur', onblur)).pause();
			this._editorColumnListeners.push(column._editorBlurHandle);

			return cmp;
		},

		_updatePropertyFromEditor: function (column, cmp, triggerEvent) {
			var value,
				id,
				editedRow;

			if (!cmp.isValid || cmp.isValid()) {
				value = this._updateProperty((cmp.domNode || cmp).parentNode,
					this._activeCell ? this._activeValue : cmp._dgridLastValue,
					this._retrieveEditorValue(column, cmp), triggerEvent);

				if (this._activeCell) { // for editors with editOn defined
					this._activeValue = value;
				}
				else { // for always-on editors, update _dgridLastValue immediately
					cmp._dgridLastValue = value;
				}

				if (cmp.type === 'radio' && cmp.name && !column.editOn && column.field) {
					editedRow = this.row(cmp);

					// Update all other rendered radio buttons in the group
					query('input[type=radio][name=' + cmp.name + ']', this.contentNode).forEach(function (radioBtn) {
						var row = this.row(radioBtn);
						// Only update _dgridLastValue and the dirty data if it exists
						// and is not already false
						if (radioBtn !== cmp && radioBtn._dgridLastValue) {
							radioBtn._dgridLastValue = false;
							if (this.updateDirty) {
								this.updateDirty(row.id, column.field, false);
							}
							else {
								// update store-less grid
								row.data[column.field] = false;
							}
						}
					}, this);

					// Also update dirty data for rows that are not currently rendered
					for (id in this.dirty) {
						if (editedRow.id.toString() !== id && this.dirty[id][column.field]) {
							this.updateDirty(id, column.field, false);
						}
					}
				}
			}
		},

		_updateProperty: function (cellElement, oldValue, value, triggerEvent) {
			// Updates dirty hash and fires dgrid-datachange event for a changed value.
			var self = this;

			// test whether old and new values are inequal, with coercion (e.g. for Dates)
			if ((oldValue && oldValue.valueOf()) !== (value && value.valueOf())) {
				var cell = this.cell(cellElement);
				var row = cell.row;
				var column = cell.column;
				// Re-resolve cellElement in case the passed element was nested
				cellElement = cell.element;

				if (column.field && row) {
					var eventObject = {
						grid: this,
						cell: cell,
						oldValue: oldValue,
						value: value,
						bubbles: true,
						cancelable: true
					};
					if (triggerEvent && triggerEvent.type) {
						eventObject.parentType = triggerEvent.type;
					}

					if (on.emit(cellElement, 'dgrid-datachange', eventObject)) {
						if (this.updateDirty) {
							// for OnDemandGrid: update dirty data, and save if autoSave is true
							this.updateDirty(row.id, column.field, value);
							// perform auto-save (if applicable) in next tick to avoid
							// unintentional mishaps due to order of handler execution
							if (column.autoSave) {
								setTimeout(function () {
									self._trackError('save');
								}, 0);
							}
						}
						else {
							// update store-less grid
							row.data[column.field] = value;
						}
					}
					else {
						// Otherwise keep the value the same
						// For the sake of always-on editors, need to manually reset the value
						var cmp;
						if ((cmp = cellElement.widget)) {
							// set _dgridIgnoreChange to prevent an infinite loop in the
							// onChange handler and prevent dgrid-datachange from firing
							// a second time
							cmp._dgridIgnoreChange = true;
							cmp.set('value', oldValue);
							setTimeout(function () {
								cmp._dgridIgnoreChange = false;
							}, 0);
						}
						else if ((cmp = cellElement.input)) {
							this._updateInputValue(cmp, oldValue);
						}

						return oldValue;
					}
				}
			}
			return value;
		},

		_updateInputValue: function (input, value) {
			// summary:
			//		Updates the value of a standard input, updating the
			//		checked state if applicable.

			input.value = value;
			if (input.type === 'radio' || input.type === 'checkbox') {
				input.checked = input.defaultChecked = !!value;
			}
		},

		_retrieveEditorValue: function (column, cmp) {
			// summary:
			//		Intermediary between _convertEditorValue and
			//		_updatePropertyFromEditor.

			if (typeof cmp.get === 'function') { // widget
				return this._convertEditorValue(cmp.get('value'));
			}
			else { // HTML input
				return this._convertEditorValue(
					cmp[cmp.type === 'checkbox' || cmp.type === 'radio' ? 'checked' : 'value']);
			}
		},

		_convertEditorValue: function (value, oldValue) {
			// summary:
			//		Contains default logic for translating values from editors;
			//		tries to preserve type if possible.

			if (typeof oldValue === 'number') {
				value = isNaN(value) ? value : parseFloat(value);
			}
			else if (typeof oldValue === 'boolean') {
				value = value === 'true' ? true : value === 'false' ? false : value;
			}
			else if (oldValue instanceof Date) {
				var asDate = new Date(value);
				value = isNaN(asDate.getTime()) ? value : asDate;
			}
			return value;
		}
	});
});
