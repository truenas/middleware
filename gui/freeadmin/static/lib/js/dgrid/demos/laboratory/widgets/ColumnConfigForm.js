define([
	'dojo/_base/array',
	'dojo/_base/declare',
	'dojo/_base/lang',
	'dojo/dom-class',
	'dojo/on',
	'dojo/query',
	'dojo/string',
	'dojo/topic',
	'dijit/registry',
	'dijit/_WidgetBase',
	'dijit/_TemplatedMixin',
	'dijit/_WidgetsInTemplateMixin',
	'dijit/form/_FormMixin',
	'./_ResizeMixin',
	'../data/config',
	'dojo/i18n!../nls/laboratory',
	'dojo/text!./templates/ColumnConfigForm.html',
	// for template
	'dijit/form/Button',
	'dijit/form/ComboBox',
	'dijit/form/FilteringSelect',
	'dijit/form/NumberTextBox',
	'dijit/form/RadioButton',
	'dijit/form/TextBox'
], function (arrayUtil, declare, lang, domClass, on, query, string, topic, registry, _WidgetBase, _TemplatedMixin,
	_WidgetsInTemplateMixin, _FormMixin, _ResizeMixin, config, i18n, template) {

	var defaultColumnValues = {
		// Standard column properties
		field: '',
		label: '',
		className: '',
		sortable: 'true',

		// Editor properties
		editor: '',
		editOn: '',
		autoSave: 'false',
		autoSelect: 'false',
		dismissOnEnter: 'true',

		// ColumnHider properties
		hidden: 'false',
		unhidable: 'false',

		// ColumnReorder properties
		reorderable: 'true',

		// ColumnResizer properties
		resizable: 'true',

		// Selector properties
		selector: ''
	};

	return declare([ _WidgetBase, _TemplatedMixin, _WidgetsInTemplateMixin, _FormMixin, _ResizeMixin ], {
		baseClass: 'configForm column',
		templateString: template,
		i18n: i18n,
		docBaseUrl: config.docBaseUrl,

		_featureMidToNodeMap: null,

		buildRendering: function () {
			this.inherited(arguments);

			if (!this.containerNode) {
				this.containerNode = this.domNode;
			}

			var map = this._featureMidToNodeMap = {
				'dgrid/Editor': this.editorFields,
				'dgrid/extensions/ColumnHider': this.columnHiderFields,
				'dgrid/extensions/ColumnReorder': this.columnReorderFields,
				'dgrid/extensions/ColumnResizer': this.columnResizerFields,
				'dgrid/Selector': this.selectorFields
			};

			for (var k in map) {
				// Add legend labels programmatically
				var moduleName = k.slice(k.lastIndexOf('/') + 1);
				map[k].getElementsByTagName('legend')[0].innerHTML =
					string.substitute(this.i18n.moduleProperties, [ moduleName ]);
			}
		},

		postCreate: function () {
			function shouldDismiss(editor) {
				return editor ? editor.toLowerCase().indexOf('textarea') === -1 : true;
			}

			this.inherited(arguments);
			this.own(
				topic.subscribe('/feature/select', lang.hitch(this, '_onFeatureSelect')),
				on(this.doneButton, 'click', lang.hitch(this, function () {
					this.emit('close');
				})),
				this.watch('value', function (propertyName, oldValue, newValue) {
					// Let the ColumnGrid know the column config has changed so it an update the store
					topic.publish('/column/changed', newValue);
					if (newValue.editor !== oldValue.editor) {
						// Set a sane default for dismissOnEnter if switching to/from a textarea editor
						var newDismiss = shouldDismiss(newValue.editor);
						var oldDismiss = shouldDismiss(oldValue.editor);
						if (newDismiss !== oldDismiss) {
							this.set('value', lang.mixin(newValue, { dismissOnEnter: '' + newDismiss }));
						}
					}
				})
			);
		},

		_setValueAttr: function (value) {
			// Use default values for any unspecified fields
			this.inherited(arguments, [lang.mixin(lang.clone(defaultColumnValues), value)]);
			// Store the id - _FormMixin will discard this value, but we need it to persist the data back to the store
			this._id = value.id;
		},

		_getValueAttr: function () {
			var returnValue = this.inherited(arguments);
			var propertyName, k;

			for (k in this._getHiddenFieldNames()) {
				delete returnValue[k];
			}

			// Omit properties with default values
			for (propertyName in returnValue) {
				if (returnValue[propertyName] === defaultColumnValues[propertyName]) {
					delete returnValue[propertyName];
				}
			}

			// Restore the id
			returnValue.id = this._id;

			return returnValue;
		},

		_getHiddenFieldNames: function () {
			var hiddenFieldNames = {};
			// Remove values from hidden fields
			query('fieldset.dijitHidden', this.domNode).forEach(function (fieldset) {
				arrayUtil.forEach(registry.findWidgets(fieldset), function (childWidget) {
					hiddenFieldNames[childWidget.name] = true;
				});
			});

			return hiddenFieldNames;
		},

		_onFeatureSelect: function (featureMid, isEnabled) {
			var featureNode = this._featureMidToNodeMap[featureMid];

			if (featureNode) {
				domClass.toggle(featureNode, 'dijitHidden', !isEnabled);

				if (!isEnabled) {
					// Close the dialog so input fields will reset if the user reenables the feature.
					this.emit('close');
					topic.publish('/columnConfig/hidden', this._getHiddenFieldNames());
				}
			}
		},

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
