define([
	'dojo/_base/declare',
	'dojo/_base/lang',
	'dojo/dom-construct',
	'dojo/topic',
	'dojo/store/Memory',
	'./ConfigForm',
	'dojo/text!./templates/Tree.html',
	'dgrid/Tree',
	// for template
	'dijit/form/FilteringSelect',
	'dijit/form/RadioButton'
], function (declare, lang, domConstruct, topic, Memory, ConfigForm, template, Tree) {
	return declare(ConfigForm, {
		templateString: template,
		defaultsObject: Tree.prototype,

		postCreate: function () {
			this.inherited(arguments);

			this.own(
				topic.subscribe('/store/columns/update', lang.hitch(this, '_updateColumnNames'))
			);
		},

		_updateColumnNames: function (columnStore) {
			var self = this;
			var data = [];
			var firstValue;

			columnStore.fetch().forEach(function (column) {
				if (!firstValue) {
					firstValue = column.field;
				}
				data.push({
					id: column.field,
					name: column.field
				});
			}).then(function () {
				self.expandoSelect.set('store', new Memory({ data: data }));
				// Select the first column by default
				// (in case the user selects tree without first visiting the options)
				self.expandoSelect.set('value', firstValue);
			});
		},

		_getValueAttr: function () {
			var returnValue = this.inherited(arguments);

			// The renderExpando property needs to be specified on the column definition
			// (it's not a grid config property)
			delete returnValue.renderExpando;

			return returnValue;
		},

		_getExpandoColumnAttr: function () {
			return this.expandoSelect.get('value');
		}
	});
});
