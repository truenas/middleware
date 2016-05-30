define([
	'dojo/_base/declare',
	'dojo/_base/lang',
	'dojo/dom-class',
	'dijit/_WidgetBase',
	'./ColumnConfigForm',
	'./ColumnGrid'
], function (declare, lang, domClass, _WidgetBase, ColumnConfigForm, ColumnGrid) {
	return declare(_WidgetBase, {
		baseClass: 'columnEditor',

		buildRendering: function () {
			this.inherited(arguments);

			this.columnGrid = new ColumnGrid().placeAt(this.domNode);
			this.form = new ColumnConfigForm().placeAt(this.domNode);
		},

		postCreate: function () {
			this.inherited(arguments);

			this.form.on('close', lang.hitch(this, '_showGrid'));
			this.columnGrid.on('editcolumn', lang.hitch(this, '_onEditColumn'));
		},

		startup: function () {
			if (this._started) {
				return;
			}
			this.inherited(arguments);

			this.columnGrid.startup();
			this.form.startup();
		},

		_getColumnsAttr: function () {
			return this.columnGrid.get('columns');
		},

		_showGrid: function () {
			domClass.remove(this.domNode, 'slid');
		},

		_onEditColumn: function (event) {
			domClass.add(this.domNode, 'slid');
			this.form.set('value', event.data);
		},

		addColumn: function (label) {
			this.columnGrid.addColumn(label);
		},

		removeColumn: function (target) {
			this.columnGrid.removeColumn(target);
		}
	});
});
