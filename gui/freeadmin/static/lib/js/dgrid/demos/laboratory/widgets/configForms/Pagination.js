define([
	'dojo/_base/declare',
	'./ConfigForm',
	'dojo/text!./templates/Pagination.html',
	'dgrid/extensions/Pagination',
	// for template
	'dijit/form/MultiSelect',
	'dijit/form/RadioButton'
], function (declare, ConfigForm, template, Pagination) {
	return declare(ConfigForm, {
		templateString: template,
		defaultsObject: Pagination.prototype
	});
});
