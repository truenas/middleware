define([
	'dojo/_base/declare',
	'./ConfigForm',
	'dojo/text!./templates/ColumnResizer.html',
	'dgrid/extensions/ColumnResizer',
	// for template
	'dijit/form/NumberTextBox',
	'dijit/form/RadioButton'
], function (declare, ConfigForm, template, ColumnResizer) {
	return declare(ConfigForm, {
		templateString: template,
		defaultsObject: ColumnResizer.prototype
	});
});
