define([
	'dojo/_base/declare',
	'dojo/aspect',
	'dojo/on',
	'dojo/has',
	'./Selection',
	'put-selector/put'
], function (declare, aspect, listen, has, Selection, put) {

	return declare(Selection, {
		// summary:
		//		Add cell level selection capabilities to a grid. The grid will have a selection property and
		//		fire "dgrid-select" and "dgrid-deselect" events.

		// ensure we don't select when an individual cell is not identifiable
		selectionDelegate: '.dgrid-cell',

		_selectionTargetType: 'cells',

		_select: function (cell, toCell, value) {
			var i,
				id;
			if (typeof value === 'undefined') {
				// default to true
				value = true;
			}
			if (typeof cell !== 'object' || !('element' in cell)) {
				cell = this.cell(cell);
			}
			else if (!cell.row) {
				// Row object was passed instead of cell
				if (value && typeof value === 'object') {
					// value is a hash of true/false values
					for (id in value) {
						this._select(this.cell(cell.id, id), null, value[id]);
					}
				}
				else {
					// Select/deselect all columns in row
					for (id in this.columns) {
						this._select(this.cell(cell.id, id), null, value);
					}
				}
				return;
			}
			if (this.allowSelect(cell)) {
				var selection = this.selection,
					rowId = cell.row.id,
					previousRow = selection[rowId];
				if (!cell.column) {
					for (i in this.columns) {
						this._select(this.cell(rowId, i), null, value);
					}
					return;
				}
				var previous = previousRow && previousRow[cell.column.id];
				if (value === null) {
					// indicates a toggle
					value = !previous;
				}
				var element = cell.element;
				previousRow = previousRow || {};
				previousRow[cell.column.id] = value;
				this.selection[rowId] = previousRow;

				// Check for all-false objects to see if it can be deleted.
				// This prevents build-up of unnecessary iterations later.
				var hasSelected = false;
				for (i in previousRow) {
					if (previousRow[i] === true) {
						hasSelected = true;
						break;
					}
				}
				if (!hasSelected) {
					delete this.selection[rowId];
				}

				if (element) {
					// add or remove classes as appropriate
					if (value) {
						put(element, '.dgrid-selected' +
							(this.addUiClasses ? '.ui-state-active' : ''));
					}
					else {
						put(element, '!dgrid-selected!ui-state-active');
					}
				}
				/* jshint eqeqeq: false */
				// This comparison could coerce if previous is undefined; TODO: rewrite
				if (value != previous && element) {
					this._selectionEventQueues[(value ? '' : 'de') + 'select'].push(cell);
				}
				if (toCell) {
					if (!toCell.element) {
						toCell = this.cell(toCell);
					}

					if (!toCell || !toCell.row) {
						this._lastSelected = element;
						console.warn('The selection range has been reset because the ' +
							'beginning of the selection is no longer in the DOM. ' +
							'If you are using OnDemandList, you may wish to increase ' +
							'farOffRemoval to avoid this, but note that keeping more nodes ' +
							'in the DOM may impact performance.');
						return;
					}

					var toElement = toCell.element;
					var fromElement = cell.element;
					// Find if it is earlier or later in the DOM
					var direction = this._determineSelectionDirection(fromElement, toElement);
					if (!direction) {
						// The original element was actually replaced
						toCell = this.cell(
							document.getElementById(toCell.row.element.id), toElement.columnId);
						toElement = toCell && toCell.element;
						direction = this._determineSelectionDirection(fromElement, toElement);
					}
					// now we determine which columns are in the range
					var idFrom = cell.column.id,
						idTo = toCell.column.id,
						started,
						columnIds = [];

					for (id in this.columns) {
						if (started) {
							columnIds.push(id);
						}
						if (id === idFrom && (idFrom = columnIds) ||
								id === idTo && (idTo = columnIds)) {
							// Once found, mark it off so we don't hit it again
							columnIds.push(id);
							if (started || (idFrom == columnIds && id == idTo)) {
								// We are done if we hit the last ID, or if the IDs are the same
								break;
							}
							started = true;
						}
					}
					// now we iterate over rows
					var row = cell.row,
						nextNode = row.element;
					toElement = toCell.row.element;
					do {
						// looping through each row..
						// and now loop through each column to be selected
						for (i = 0; i < columnIds.length; i++) {
							cell = this.cell(nextNode, columnIds[i]);
							this._select(cell, null, value);
						}
						if (nextNode == toElement) {
							break;
						}
					} while ((nextNode = cell.row.element[direction]));
				}
			}
		},

		_determineSelectionDirection: function () {
			// Extend Selection to return next/previousSibling instead of down/up,
			// given how CellSelection#_select is written
			var result = this.inherited(arguments);
			if (result === 'down') {
				return 'nextSibling';
			}
			if (result === 'up') {
				return 'previousSibling';
			}
			return result;
		},

		isSelected: function (object, columnId) {
			// summary:
			//		Returns true if the indicated cell is selected.

			if (typeof object === 'undefined' || object === null) {
				return false;
			}
			if (!object.element) {
				object = this.cell(object, columnId);
			}

			// First check whether the given cell is indicated in the selection hash;
			// failing that, check if allSelected is true (testing against the
			// allowSelect method if possible)
			var rowId = object.row.id;
			if (rowId in this.selection) {
				return !!this.selection[rowId][object.column.id];
			}
			else {
				return this.allSelected && (!object.row.data || this.allowSelect(object));
			}
		},
		clearSelection: function (exceptId) {
			// disable exceptId in cell selection, since it would require double parameters
			exceptId = false;
			this.inherited(arguments);
		}
	});
});
