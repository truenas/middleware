define([
	'dojo/_base/array',
	'dojo/_base/declare',
	'dojo/_base/lang',
	'dojo/mouse',
	'dojo/on',
	'dojo/query',
	'dojo/topic',
	'dijit/_WidgetBase',
	'dijit/_TemplatedMixin',
	'dijit/_WidgetsInTemplateMixin',
	'./_ResizeMixin',
	'dijit/Tooltip',
	'dijit/form/CheckBox',
	'dgrid/Grid',
	'dgrid/Editor',
	'dgrid/extensions/DijitRegistry',
	'../grid/SingleQuery',
	'dojo/i18n!../nls/laboratory',
	'dojo/text!./templates/FeatureGrid.html',
	// Widgets in template
	'dijit/form/Form',
	'dijit/form/RadioButton'
], function (arrayUtil, declare, lang, mouse, on, query, topic,
		_WidgetBase, _TemplatedMixin, _WidgetsInTemplateMixin, _ResizeMixin,
		Tooltip, CheckBox, Grid, Editor, DijitRegistry, SingleQuery, i18n, template) {

	function renderLabelCell (item, value, node) {
		// Render the label cell, adding the doc link, tooltip icon, and config icon when appropriate
		var cellHtml = '<a class="featureLabel" href="#">' + item.label + '</a>';

		// If configModule has not been defined there's no config widget to display
		if (item.configLevel === 'grid' && item.configModule) {
			cellHtml = cellHtml + ' <i class="icon-gear"></i>';
		}

		node.innerHTML = cellHtml;
	}

	var CustomGrid = declare([ Grid, SingleQuery, Editor, DijitRegistry ], {
		gridTypeForm: null, // Passed from FeatureGrid when instantiated
		showHeader: false,
		columns: {
			selected: {
				label: '',
				editor: CheckBox,
				editorArgs: {
					value: true
				},
				autoSave: true,
				sortable: false
			},
			label: {
				renderCell: renderLabelCell,
				sortable: false
			}
		},

		postCreate: function () {
			this.inherited(arguments);

			this.on('dgrid-datachange', lang.hitch(this, '_onDataChange'));
			this.on('.featureLabel:click', lang.hitch(this, '_onFeatureLabelClick'));
			this.on(on.selector('.field-label', mouse.enter), lang.hitch(this, '_showInfoTip'));
			this.on(on.selector('.field-label', mouse.leave), lang.hitch(this, '_hideInfoTip'));
		},

		_onFeatureLabelClick: function (event) {
			event.preventDefault();
			// Since we are using Dijit checkbox editors, updating one's checked state will fire
			// change handlers, which will route into _onDataChange below
			var checkbox = this.cell(this.row(event), 'selected').element.widget;
			if (!checkbox.get('disabled')) {
				checkbox.set('checked', !checkbox.get('checked'));
			}
		},

		_onDataChange: function (event) {
			var store = this._store;
			var selectedMid = event.cell.row.data.mid;
			var otherRow;

			// Let the ColumnConfigForm know that a feature is selected/deselected so it can show/hide its config
			topic.publish('/feature/select', event.cell.row.data.mid, event.value);

			// Enforce mutual exclusivity between CellSelection-Selection and Pagination-OnDemandGrid
			switch (selectedMid) {
				case 'dgrid/Selection':
					if (event.value) {
						otherRow = store.filter({ mid: 'dgrid/CellSelection', selected: true }).fetchSync()[0];

						if (otherRow) {
							otherRow.selected = false;
							store.put(otherRow);
						}
					}

					break;

				case 'dgrid/CellSelection':
					if (event.value) {
						otherRow = store.filter({ mid: 'dgrid/Selection', selected: true }).fetchSync()[0];

						if (otherRow) {
							otherRow.selected = false;
							store.put(otherRow);
						}
					}

					break;

				case 'dgrid/extensions/Pagination':
					otherRow = store.filter({ mid: 'dgrid/OnDemandGrid' }).fetchSync()[0];

					// If the user clicks to select Pagination...
					if (event.value) {
						// ...and OnDemandGrid was not selected, then we can assume gridType is array and we need to
						// switch it to store-based (OnDemandGrid)
						if (!otherRow.selected) {
							this.gridTypeForm.set('value', { gridType: 'OnDemandGrid' });
						}
						else {
							// ...but we actually want to deselect OnDemandGrid
							otherRow.selected = false;
							store.put(otherRow);
						}
					}
					// If the user clicks to deselect Pagination then we want to select OnDemandGrid
					else {
						otherRow.selected = true;
						store.put(otherRow);
					}

					break;

				case 'dgrid/Selector':
					// Fall through
				case 'dgrid/Tree':
					// Fall through
				case 'dgrid/extensions/DnD':
					// If the user selects a mixin or extension that requires a store,
					// make sure a store-based config is active:
					// 1. If OnDemandGrid or Pagination is already selected, a store is in use
					// 2. Otherwise select OnDemandGrid
					if (event.value) {
						otherRow = store.filter({
							mid: /(OnDemandGrid|Pagination)$/,
							selected: true
						}).fetchSync();

						if (!otherRow.length) {
							this.gridTypeForm.set('value', { gridType: 'OnDemandGrid' });
						}
					}

					break;
			}
		},

		insertRow: function (object) {
			// This method ensures that the editor (checkbox) rendered for the Grid and OnDemandGrid rows
			// is always disabled

			var rowNode = this.inherited(arguments);
			var cell = this.cell(rowNode, 'selected');
			var mid = object.mid;

			if (mid === 'dgrid/Grid' || mid === 'dgrid/OnDemandGrid') {
				cell.element.widget.set('disabled', true);
			}

			return rowNode;
		},

		_showInfoTip: function (event) {
			var row = this.row(event);
			var info = row.data.info;
			if (info) {
				Tooltip.show(info, row.element);
			}
		},

		_hideInfoTip: function (event) {
			Tooltip.hide(this.row(event).element);
		}
	});

	return declare([ _WidgetBase, _TemplatedMixin, _WidgetsInTemplateMixin, _ResizeMixin ], {
		className: 'featureGridContainer',
		templateString: template,
		i18n: i18n,

		store: null,
		featureType: null,

		buildRendering: function () {
			this.inherited(arguments);
			this.grid = new CustomGrid({
				className: 'featureGrid dgrid-autoheight',
				_store: this.store,
				collection: this.store.filter({ featureType: this.featureType }),
				gridTypeForm: this.gridTypeForm
			}, this.gridNode);
			this._startupWidgets.push(this.grid);
		},

		postCreate: function () {
			var self = this;
			this.inherited(arguments);

			this.own(
				this.grid.on('.icon-gear:click', function (event) {
					self.emit('configure-module', { mid: self.grid.row(event).data.mid });
				})
			);
		},

		_setGridModuleAttr: function (module) {
			// 'module' should be either 'Grid' or 'OnDemandGrid'

			var store = this.store;
			var items;

			if (module === 'OnDemandGrid') {
				// Select OnDemandGrid, unless Pagination is already selected
				items = store.filter({
					mid: 'dgrid/extensions/Pagination',
					selected: true
				}).fetchSync();

				if (!items.length) {
					items = store.filter({ mid: 'dgrid/OnDemandGrid' }).fetchSync();
					items[0].selected = true;
					store.put(items[0]);
				}
			}
			else {
				// Deselect any modules that require a store
				items = store.filter({
					mid: /\/(OnDemandGrid|Selector|Tree|extensions\/(DnD|Pagination))$/,
					selected: true
				}).fetchSync();

				arrayUtil.forEach(items, function (item) {
					item.selected = false;
					store.put(item);
				});
			}
		},

		_setFeatureTypeAttr: function (featureType){
			this.grid.set('collection', this.store.filter({ featureType: featureType }));
		}
	});
});
