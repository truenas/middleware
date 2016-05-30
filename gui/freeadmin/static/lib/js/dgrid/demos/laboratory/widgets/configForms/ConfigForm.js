define([
	'dojo/_base/array',
	'dojo/_base/declare',
	'dojo/_base/lang',
	'dojo/dom-construct',
	'dojo/on',
	'dojo/string',
	'dojo/topic',
	'dijit/_WidgetBase',
	'dijit/_TemplatedMixin',
	'dijit/_WidgetsInTemplateMixin',
	'dijit/form/_FormMixin',
	'../_ResizeMixin',
	'dijit/form/Button',
	'dojo/i18n!../../nls/laboratory'
], function (arrayUtil, declare, lang, domConstruct, on, string, topic, _WidgetBase, _TemplatedMixin,
		_WidgetsInTemplateMixin, _FormMixin, _ResizeMixin, Button, i18n) {

	return declare([ _WidgetBase, _TemplatedMixin, _WidgetsInTemplateMixin, _FormMixin, _ResizeMixin ], {
		i18n: i18n,
		baseClass: 'configForm',

		// This should be over-ridden by sub-classes and define an object with properties that specify default
		// configuration values for the module
		defaultsObject: {},

		documentationUrl: '',

		moduleName: '',

		buildRendering: function () {
			this.inherited(arguments);

			if (!this.containerNode) {
				this.containerNode = this.domNode;
			}

			// Add button bar to the top of each config form (including subclasses)
			var buttonBar = domConstruct.create('div', {
				className: 'buttonBar'
			});

			this.doneButton = new Button({
				label: i18n.done
			}).placeAt(buttonBar);

			this._startupWidgets.push(this.doneButton);

			domConstruct.place(buttonBar, this.domNode, 'first');

			if (this.moduleName) {
				// Populate "x configuration" and "x documentation" strings
				if (this.legendNode) {
					this.legendNode.innerHTML =
						string.substitute(this.i18n.moduleConfiguration, [ this.moduleName ]);
				}

				if (this.documentationUrl) {
					var documentationUrlTemplate = '<a href="' + this.documentationUrl + '" target="_blank">' +
						string.substitute(this.i18n.moduleDocumentation, [ this.moduleName ]) + '</a>';
					domConstruct.place(documentationUrlTemplate, this.domNode);
				}
			}
		},

		postCreate: function () {
			this.own(
				on(this.doneButton, 'click', lang.hitch(this, function () {
					this.emit('close');
				})),
				this.watch('value', lang.hitch(this, function () {
					// Let the Laboratory know that it should update the demo display (grid or generated code)
					topic.publish('/configuration/changed');
				}))
			);
		},

		startup: function () {
			this.inherited(arguments);

			// This must be done in startup: _FormMixin doesn't set this._descendants until startup
			this._setDefaultValues();
		},

		_getValueAttr: function () {
			var returnValue = this.inherited(arguments);
			var property;

			// Remove properties that just give the default behavior
			for (property in returnValue) {
				// Values from RadioButtons are strings; convert true/false strings to boolean values
				if (returnValue[property] === 'true') {
					returnValue[property] = true;
				}
				else if (returnValue[property] === 'false') {
					returnValue[property] = false;
				}

				if (returnValue[property] === this.defaultsObject[property]) {
					delete returnValue[property];
				}
			}

			return returnValue;
		},

		_setDefaultValues: function () {
			var defaultValues = {};

			arrayUtil.forEach(this._descendants, function (widget) {
				if (widget.name && widget.name in this.defaultsObject) {
					defaultValues[widget.name] = '' + this.defaultsObject[widget.name];
				}
			}, this);

			// TODO: it would be ideal to ignore this in the 'value' watcher registered in postCreate
			// but it's difficult since `this.set` fires change handlers async and does not return a promise
			this.set('value', defaultValues);
		}
	});
});
