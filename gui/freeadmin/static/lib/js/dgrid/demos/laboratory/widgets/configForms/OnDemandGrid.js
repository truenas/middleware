define([
	'dojo/_base/declare',
	'./ConfigForm',
	'dojo/text!./templates/OnDemandGrid.html',
	'dgrid/OnDemandGrid',
	// for template
	'dijit/form/NumberTextBox',
	'dijit/form/RadioButton',
	'dijit/form/FilteringSelect'
], function (declare, ConfigForm, template, OnDemandGrid) {
	return declare(ConfigForm, {
		templateString: template,
		defaultsObject: OnDemandGrid.prototype,

		_getValueAttr: function () {
			var returnValue = this.inherited(arguments);
			var numericValue;

			if ('maxEmptySpace' in returnValue) {
				numericValue = +returnValue.maxEmptySpace;

				if (numericValue !== this.defaultsObject.maxEmptySpace &&
					!isNaN(numericValue)) {
					returnValue.maxEmptySpace = numericValue;
				}
				else {
					delete returnValue.maxEmptySpace;
				}
			}

			return returnValue;
		}
	});
});
