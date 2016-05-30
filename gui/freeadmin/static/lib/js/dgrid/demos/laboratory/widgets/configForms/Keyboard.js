define([
	'dojo/_base/declare',
	'./ConfigForm',
	'dojo/text!./templates/Keyboard.html',
	'dgrid/Grid',
	'dgrid/Keyboard',
	// for template
	'dijit/form/NumberTextBox',
	'dijit/form/RadioButton'
], function (declare, ConfigForm, template, Grid, Keyboard) {
	return declare(ConfigForm, {
		templateString: template,
		defaultsObject: declare([ Grid, Keyboard ]).prototype
	});
});
