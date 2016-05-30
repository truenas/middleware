define([
	'dojo/_base/declare',
	'dojo/_base/lang',
	'dojo/_base/sniff',
	'./Selection',
	'put-selector/put'
], function (declare, lang, has, Selection, put) {

	return declare(Selection, {
		// summary:
		//		Adds an input field (checkbox or radio) to a column that when checked, selects the row
		//		that contains the input field.  To enable, add a "selector" property to a column definition.
		//
		// description:
		//		The selector property should contain "checkbox", "radio", or be a function that renders the input.
		//		If set to "radio", the input field will be a radio button and only one input in the column will be
		//		checked.  If the value of selector is a function, then the function signature is
		//		renderSelectorInput(column, value, cell, object) where:
		//		* column - the column definition
		//		* value - the cell's value
		//		* cell - the cell's DOM node
		//		* object - the row's data object
		//		The custom renderSelectorInput function must return an input field.

		postCreate: function () {
			this.inherited(arguments);

			// Register one listener at the top level that receives events delegated
			this.on('.dgrid-selector:click,.dgrid-selector:keydown', lang.hitch(this, '_handleSelectorClick'));
			// Register listeners to the select and deselect events to change the input checked value
			this.on('dgrid-select', lang.hitch(this, '_changeSelectorInput', true));
			this.on('dgrid-deselect', lang.hitch(this, '_changeSelectorInput', false));
		},

		_defaultRenderSelectorInput: function (column, selected, cell, object) {
			var parent = cell.parentNode;
			var grid = column.grid;

			// Must set the class name on the outer cell in IE for keystrokes to be intercepted
			put(parent && parent.contents ? parent : cell, '.dgrid-selector');
			var input = cell.input || (cell.input = put(cell, 'input[type=' + column.selector + ']', {
				tabIndex: isNaN(column.tabIndex) ? -1 : column.tabIndex,
				disabled: !grid.allowSelect(grid.row(object)),
				checked: selected
			}));
			input.setAttribute('aria-checked', selected);

			return input;
		},

		_configureSelectorColumn: function (column) {
			var self = this;
			var selector = column.selector;

			this._selectorColumns.push(column);
			this._selectorSingleRow = this._selectorSingleRow || column.selector === 'radio';

			var renderSelectorInput = typeof selector === 'function' ?
				selector : this._defaultRenderSelectorInput;

			column.sortable = false;

			column.renderCell = function (object, value, cell) {
				var row = object && self.row(object);
				value = row && self.selection[row.id];
				renderSelectorInput(column, !!value, cell, object);
			};

			column.renderHeaderCell = function (th) {
				var label = 'label' in column ? column.label : column.field || '';

				if (column.selector === 'radio' || !self.allowSelectAll) {
					th.appendChild(document.createTextNode(label));
				}
				else {
					column._selectorHeaderCheckbox = renderSelectorInput(column, false, th, {});
					self._hasSelectorHeaderCheckbox = true;
				}
			};
		},

		_handleSelectorClick: function (event) {
			// Avoid double-triggering code below due to space key on input automatically triggering click (#731)
			if (event.target.nodeName === 'INPUT' && event.type === 'keydown' && event.keyCode === 32) {
				return;
			}

			var cell = this.cell(event);
			var row = cell.row;

			// We would really only care about click, since other input sources like spacebar
			// trigger a click, but the click event doesn't provide access to the shift key in firefox, so
			// listen for keydown as well to get an event in firefox that we can properly retrieve
			// the shiftKey property
			if (event.type === 'click' || event.keyCode === 32 ||
				(!has('opera') && event.keyCode === 13) || event.keyCode === 0) {

				this._selectionTriggerEvent = event;

				if (row) {
					if (this.allowSelect(row)) {
						var lastRow = this._lastSelected && this.row(this._lastSelected);

						if (this._selectorSingleRow) {
							if (!lastRow || lastRow.id !== row.id) {
								this.clearSelection();
								this.select(row, null, true);
								this._lastSelected = row.element;
							}
						}
						else {
							if (row) {
								if (event.shiftKey) {
									// Make sure the last input always ends up checked for shift key
									this._changeSelectorInput(true, {rows: [row]});
								}
								else {
									// No shift key, so no range selection
									lastRow = null;
								}
								lastRow = event.shiftKey ? lastRow : null;
								this.select(lastRow || row, row, lastRow ? undefined : null);
								this._lastSelected = row.element;
							}
						}
					}
				}
				else {
					// No row resolved; must be the select-all checkbox.
					this[this.allSelected ? 'clearSelection' : 'selectAll']();
				}

				this._selectionTriggerEvent = null;
			}
		},

		_changeSelectorInput: function (value, event) {
			if (this._selectorColumns.length) {
				this._updateRowSelectors(value, event);
			}
			if (this._hasSelectorHeaderCheckbox) {
				this._updateHeaderCheckboxes();
			}
		},

		_updateRowSelectors: function (value, event) {
			var rows = event.rows;
			var lenRows = rows.length;
			var lenCols = this._selectorColumns.length;

			for (var iRows = 0; iRows < lenRows; iRows++) {
				for (var iCols = 0; iCols < lenCols; iCols++) {
					var column = this._selectorColumns[iCols];
					var element = this.cell(rows[iRows], column.id).element;
					if (!element) {
						// Skip if row has been entirely removed
						continue;
					}
					element = (element.contents || element).input;
					if (element && !element.disabled) {
						// Only change the value if it is not disabled
						element.checked = value;
						element.setAttribute('aria-checked', value);
					}
				}
			}
		},

		_updateHeaderCheckboxes: function () {
			/* jshint eqeqeq: false */
			var lenCols = this._selectorColumns.length;
			for (var iCols = 0; iCols < lenCols; iCols++) {
				var column = this._selectorColumns[iCols];
				var state = 'false';
				var selection;
				var mixed;
				var selectorHeaderCheckbox = column._selectorHeaderCheckbox;
				if (selectorHeaderCheckbox) {
					selection = this.selection;
					mixed = false;
					// See if the header checkbox needs to be indeterminate
					for (var i in selection) {
						// If there is anything in the selection, than it is indeterminate
						// (Intentionally coerce since selection[i] can be undefined)
						if (selection[i] != this.allSelected) {
							mixed = true;
							break;
						}
					}
					selectorHeaderCheckbox.indeterminate = mixed;
					selectorHeaderCheckbox.checked = this.allSelected;
					if (mixed) {
						state = 'mixed';
					}
					else if (this.allSelected) {
						state = 'true';
					}
					selectorHeaderCheckbox.setAttribute('aria-checked', state);
				}
			}
		},

		configStructure: function () {
			this.inherited(arguments);
			var columns = this.columns;
			this._selectorColumns = [];
			this._hasSelectorHeaderCheckbox = this._selectorSingleRow = false;

			for (var k in columns) {
				if (columns[k].selector) {
					this._configureSelectorColumn(columns[k]);
				}
			}
		},

		_handleSelect: function (event) {
			// Ignore the default select handler for events that originate from the selector column
			var column = this.cell(event).column;
			if (!column || !column.selector) {
				this.inherited(arguments);
			}
		}
	});
});
