define([
	'dojo/_base/declare',
	'./ConfigForm',
	'dojo/text!./templates/Selection.html',
	'dgrid/Selection',
	// for template
	'dijit/form/FilteringSelect',
	'dijit/form/RadioButton'
], function (declare, ConfigForm, template, Selection) {
	return declare(ConfigForm, {
		templateString: template,
		defaultsObject: Selection.prototype,

		_clearField: function (event) {
			var fieldName = event.target.getAttribute('data-field-name');
			var formValue = this.get('value');

			if (!fieldName) {
				return;
			}

			if (fieldName in formValue) {
				formValue[fieldName] = '';
				this.set('value', formValue);
			}
		}
	});
});
