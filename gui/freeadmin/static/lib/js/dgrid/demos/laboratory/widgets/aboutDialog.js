define([
	'dojo/_base/declare',
	'dojo/string',
	'dijit/_WidgetBase',
	'dijit/_TemplatedMixin',
	'dijit/Dialog',
	'dojo/text!./templates/AboutDialog.html',
	'dojo/i18n!../nls/laboratory',
	'../data/config'
], function (declare, string, _WidgetBase, _TemplatedMixin, Dialog, template, i18n, config) {
	var AboutContent = declare([ _WidgetBase, _TemplatedMixin ], {
		templateString: template,
		i18n: i18n,

		buildRendering: function () {
			this.inherited(arguments);
			this.appInformationNode.innerHTML = string.substitute(i18n.appInformation, config);
		}
	});

	return new Dialog({
		'class': 'aboutDialog',
		content: new AboutContent(),
		draggable: false,
		title: i18n.aboutTitle
	});
});