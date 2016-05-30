define([
	'dojo/_base/declare',
	'./ConfigForm',
	'dojo/text!./templates/Grid.html',
	'dgrid/Grid',
	// for template
	'dijit/form/RadioButton',
	'dijit/form/TextBox'
], function (declare, ConfigForm, template, Grid) {
	return declare(ConfigForm, {
		templateString: template,
		defaultsObject: Grid.prototype
	});
});
