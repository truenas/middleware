define([
	'require',
	'dojo/_base/array',
	'dojo/_base/declare',
	'dojo/_base/lang',
	'dojo/dom-class',
	'dojo/query',
	'dojo/string',
	'dojo/on',
	'dojo/topic',
	'dijit/_WidgetBase',
	'dijit/_TemplatedMixin',
	'dijit/_WidgetsInTemplateMixin',
	'dijit/form/TextBox',
	'dijit/form/SimpleTextarea',
	'dstore/Memory',
	'dstore/Trackable',
	'dstore/Tree',
	'./aboutDialog',
	'./ColumnEditor',
	'./FeatureEditor',
	'../util/toJavaScript',
	'../data/config',
	'dojo/i18n!../nls/laboratory',
	'dojo/text!./templates/Laboratory.html',
	'dojo/text!./templates/gridCode.js',
	'dojo/query',
	// Widgets in template
	'dijit/layout/ContentPane',
	'dijit/layout/TabContainer'
], function (require, arrayUtil, declare, lang, domClass, query, string, on, topic,
		_WidgetBase, _TemplatedMixin, _WidgetsInTemplateMixin, TextBox, SimpleTextarea,
		Memory, Trackable, TreeStoreMixin, aboutDialog, ColumnEditor, FeatureEditor,
		toJavaScript, config, i18n, template, codeTemplate) {

	var NUM_ITEMS = 50;
	var dijitNameToConstructor = {
		TextBox: TextBox,
		SimpleTextarea: SimpleTextarea
	};

	return declare([ _WidgetBase, _TemplatedMixin, _WidgetsInTemplateMixin ], {
		templateString: template,
		i18n: i18n,
		docBaseUrl: config.docBaseUrl,
		dgridUrl: config.dgridUrl,

		// resourcesBaseUrl is used for image paths; toUrl includes cacheBust so strip it
		resourcesBaseUrl: require.toUrl('../resources').replace(/\?.*$/, ''),

		baseClass: 'laboratory',

		aboutVisible: true,
		aboutKey: '', // Passed from index.html if localStorage is supported

		buildRendering: function () {
			this.inherited(arguments);

			this.featureEditor = new FeatureEditor({}, this.featureEditorNode);
			this.columnEditor = new ColumnEditor({}, this.columnEditorNode);
		},

		postCreate: function () {
			this.inherited(arguments);

			this.own(
				topic.subscribe('/configuration/changed', lang.hitch(this, '_updateDemo'))
				// this.previewTabs.watch('selectedChildWidget', lang.hitch(this, '_updateDemo'))
			);

			this._selectedChildWidget = this.demoGridPane;
		},

		startup: function () {
			var columnEditor = this.columnEditor;
			this.inherited(arguments);

			this.featureEditor.startup().then(function () {
				columnEditor.startup();

				// Add a couple of columns by default;
				// wait until after FeatureEditor's startup promise resolves,
				// to give forms a chance to react to column addition/removal (e.g. Tree)
				columnEditor.addColumn('First Name');
				columnEditor.addColumn('Last Name');
			});
		},

		selectTab: function (evt) {
			var target = evt.target.getAttribute('data-target');
			query('.active', this.domNode).removeClass('active');

			query('[data-target="' + target + '"]', this.domNode).addClass('active');
			if (target !== 'columns') {
				// The Grid and Column Features "tabs" actually both show the same widget,
				// but using a different filter for its grid
				this.featureEditor.set('featureType', (target === 'gridFeatures') ? 'grid' : 'column');
				target = 'features';
			}
			query('[data-tab="' + target + '"]', this.domNode).addClass('active');
		},

		_showAbout: function (event) {
			event.preventDefault();
			aboutDialog.show();
		},

		_toggleColumns: function () {
			domClass.toggle(this.columnEditorNode, 'open');
		},

		_updateDemo: function () {
			if (this.demoGrid) {
				this.demoGrid.destroy();
			}

			this.gridCodeTextArea.value = '';

			// If no columns have been defined, then don't bother rendering an empty demo grid
			// or generating code for an empty grid
			if (this.columnEditor.get('columns').length < 1) {
				return;
			}

			if (this._selectedChildWidget === this.demoGridPane) {
				this._showDemoGrid();
			}
			else {
				this._showCode();
			}
		},

		_selectCode: function () {
			this._selectedChildWidget = this.demoCodePane;
			this.previewTabs.setAttribute('data-selected-page', 'code');
			this._updateDemo();
		},

		_selectGrid: function () {
			this._selectedChildWidget = this.demoGridPane;
			this.previewTabs.setAttribute('data-selected-page', 'grid');
			this._updateDemo();
		},

		_showCode: function () {
			this.gridCodeTextArea.value = this._generateCode();
		},

		_generateCode: function () {
			var gridConfig = {
				gridOptions: '{\n',
				dataDeclaration: '',
				dataCreation: '',
				gridRender: ''
			};
			// deps, prams, and grid modules are built as arrays then joined when assigned to gridConfig
			var dependencies = [ 'dojo/_base/declare' ];
			var callbackParams = [ 'declare' ];
			var gridModules = [];
			var gridOptions = this._generateGridOptions();
			var columnNames = [];
			var columnName;
			var treeExpandoColumn;
			var storeModules;
			var hasStore = this.featureEditor.isSelected('dgrid/OnDemandGrid') ||
				this.featureEditor.isSelected('dgrid/extensions/Pagination');

			arrayUtil.forEach(this.columnEditor.get('columns'), function (columnConfig) {
				// Convert any dijit module IDs for column.editor to constructors, and add the necessary dependencies
				var formWidgetCallbackParam = toJavaScript.formatDijitFormWidget(columnConfig.editor);
				if (formWidgetCallbackParam && callbackParams.indexOf(formWidgetCallbackParam) < 0) {
					dependencies.push(columnConfig.editor);
					callbackParams.push(formWidgetCallbackParam);
				}
			}, this);
			// The expandoColumn for Tree is a special case:
			// In the UI, it works better to present it in the grid feature config,
			// although it's really a column config option. In order to add it to the appropriate column config
			// we need to get its value
			if (this.featureEditor.isSelected('dgrid/Tree')) {
				treeExpandoColumn = this.featureEditor.get('expandoColumn');
			}

			if (hasStore) {
				storeModules = [ 'Memory', 'Trackable' ];

				if (treeExpandoColumn) {
					storeModules.push('TreeStoreMixin');
				}

				gridConfig.dataDeclaration = 'var store = new (declare([' + storeModules.join(', ') + ']))({\n' +
					'\t\tdata: createData()\n\t});';
			}
			else {
				gridConfig.dataDeclaration = 'var data = createData();';
			}

			for (columnName in gridOptions.columns) {
				columnNames.push(toJavaScript.formatPropertyName(columnName));
			}

			gridConfig.dataCreation = '\n\n\tfunction createData() {' +
				'\n\t\tvar data = [];' +
				'\n\t\tvar column;' +
				'\n\t\tvar i;' +
				'\n\t\tvar item;' + '\n' +
				'\n\t\tfor (i = 0; i < ' + NUM_ITEMS + '; i++) {' +
				'\n\t\t\titem = {};' +
				'\n\t\t\tfor (column in { ' + columnNames.join(': 1, ') + ': 1 }) {' +
				'\n\t\t\t\titem.id = i;' +
				'\n\t\t\t\titem[column] = column + \'_\' + (i + 1);' +
				'\n\t\t\t}';

			if (treeExpandoColumn) {
				gridConfig.dataCreation += '\n\t\t\tif (i > 1) {';
				gridConfig.dataCreation += '\n\t\t\t\titem.hasChildren = false;';
				gridConfig.dataCreation += '\n\t\t\t\titem.parent = i % 2;';
				gridConfig.dataCreation += '\n\t\t\t}';
			}

			gridConfig.dataCreation += '\n\t\t\tdata.push(item);' +
				'\n\t\t}' + '\n' +
				'\n\t\treturn data;' +
				'\n\t}';

			if (hasStore) {
				dependencies.push('dstore/Memory', 'dstore/Trackable');
				callbackParams.push('Memory', 'Trackable');

				if (treeExpandoColumn) {
					dependencies.push('dstore/Tree');
					callbackParams.push('TreeStoreMixin');
				}

				gridConfig.storeDeclaration = '\n\tvar store = new (declare([ Memory, Trackable ]))({\n' +
					'\t\tdata: data\n\t});\n';
				gridConfig.storeAssignment = '\n\tgrid.set(\'collection\', store);';
			}
			else {
				gridConfig.gridRender = '\n\tgrid.renderArray(data);';
			}

			// Add selected items from the feature store to the dependency list
			arrayUtil.forEach(this.featureEditor.filter({ selected: true }), function (item) {
				// Configuration for dgrid/Grid is always available since it is the base clase for OnDemandGrid
				// If OnDemandGrid is selected then we can skip adding dgrid/Grid to the dependencies
				if (item.mid === 'dgrid/Grid' && this.featureEditor.isSelected('dgrid/OnDemandGrid')) {
					return;
				}

				var moduleReference = item.mid.slice(item.mid.lastIndexOf('/') + 1);

				dependencies.push(item.mid);
				callbackParams.push(moduleReference);
				gridModules.push(moduleReference);
			}, this);

			if (hasStore) {
				gridConfig.gridOptions += '\t\tcollection: store,\n';
			}

			gridConfig.gridOptions += toJavaScript(gridOptions, { indent: 1, inline: true } );
			gridConfig.gridOptions += '\n\t}';

			gridConfig.dependencies = '\'' + dependencies.join('\',\n\t\'') + '\'';
			gridConfig.callbackParams = callbackParams.join(', ');
			gridConfig.gridModules = gridModules.join(', ');

			return string.substitute(codeTemplate, gridConfig);
		},

		_showDemoGrid: function () {
			var self = this;
			var gridOptions = this._generateGridOptions();
			var gridModules = [];
			var isTree = this.featureEditor.isSelected('dgrid/Tree');
			var data = this._generateMockData();
			var hasStore = this.featureEditor.isSelected('dgrid/OnDemandGrid') ||
				this.featureEditor.isSelected('dgrid/extensions/Pagination');

			arrayUtil.forEach(this.featureEditor.filter({ selected: true }), function (item) {
				// Configuration for dgrid/Grid is always available since it is the base clase for OnDemandGrid
				// If OnDemandGrid is selected then we can skip adding dgrid/Grid to the dependencies
				if (item.mid === 'dgrid/Grid' && this.featureEditor.isSelected('dgrid/OnDemandGrid')) {
					return;
				}

				gridModules.push(item.mid);
			}, this);

			this._fixDijitConstructors(gridOptions.columns);
			require(gridModules, function () {
				var storeModules;
				var store;

				gridOptions.className = 'demoGrid';

				if (hasStore) {
					storeModules = [ Memory, Trackable ];

					if (isTree) {
						storeModules.push(TreeStoreMixin);
					}

					store = new (declare(storeModules))({
						data: data
					});

					gridOptions.collection = isTree ? store.filter('mayHaveChildren') : store;
				}

				self.demoGrid = new (declare(Array.prototype.slice.apply(arguments)))(gridOptions);
				self.demoGridPane.innerHTML = '';
				self.demoGridPane.appendChild(self.demoGrid.domNode);
				self.demoGrid.startup();

				if (!hasStore) {
					self.demoGrid.renderArray(data);
				}
			});
		},

		_generateGridOptions: function () {
			var gridOptions = {};
			var selectedFeatures = this.featureEditor.filter({ selected: true, configLevel: 'grid' });
			var treeExpandoColumn;
			var columns = [];
			var column;
			var tempColumns;
			var numFieldName;

			if (this.featureEditor.isSelected('dgrid/Tree')) {
				treeExpandoColumn = this.featureEditor.get('expandoColumn');
			}

			arrayUtil.forEach(selectedFeatures, function (feature) {
				var moduleConfig = this.featureEditor.getModuleConfig(feature.mid);

				if (moduleConfig) {
					lang.mixin(gridOptions, moduleConfig);
				}
			}, this);

			arrayUtil.forEach(this.columnEditor.get('columns'), function (columnConfig) {
				var config = this._fixDataTypes(lang.clone(columnConfig));

				// The laboratory needs the store items to have a unique id property,
				// but we don't want to include it in our output
				delete config.id;

				if (config.field === treeExpandoColumn) {
					config.renderExpando = true;
				}
				numFieldName = numFieldName || isFinite(config.field);
				columns.push(config);
			}, this);

			if (!numFieldName) {
				// If there are no field names that are numbers, then use an object to define the columns.
				tempColumns = {};
				while ((column = columns.shift())) {
					tempColumns[column.field] = column;
					delete column.field;
				}
				columns = tempColumns;
			}

			if (this.featureEditor.isSelected('dgrid/ColumnSet')) {
				gridOptions.columnSets = [[columns]];
			}
			else {
				gridOptions.columns = columns;
			}

			return gridOptions;
		},

		// Fix data types on objects created from widget values
		// Change string 'true'/'false' values to booleans
		_fixDataTypes: function (obj) {
			var propertyName;

			if (typeof obj !== 'object') {
				return obj;
			}

			for (propertyName in obj) {
				if (obj[propertyName] === 'true') {
					obj[propertyName] = true;
				}
				else if(obj[propertyName] === 'false') {
					obj[propertyName] = false;
				}
			}

			return obj;
		},

		_generateMockData: function () {
			var mockData = [];
			var fieldNames = [];
			var i;

			arrayUtil.forEach(this.columnEditor.get('columns'), function (columnConfig) {
				fieldNames.push(columnConfig.field);
			});

			if (fieldNames.length > 0) {
				for (i = 0; i < NUM_ITEMS; i++) {
					mockData.push({});
					mockData[i].id = i;

					if (i > 1) {
						mockData[i].hasChildren = false;
						mockData[i].parent = i % 2;
					}

					arrayUtil.forEach(fieldNames, function (fieldName) {
						mockData[i][fieldName] = fieldName + '_' + (i + 1);
					});
				}
			}

			return mockData;
		},

		_fixDijitConstructors: function(obj) {
			if (obj) {
				for (var columnKey in obj) {
					var column = obj[columnKey];
					if (column && column.editor) {
						var dijitConstructorName = toJavaScript.formatDijitFormWidget(column.editor);
						if (dijitConstructorName) {
							column.editor = dijitNameToConstructor[dijitConstructorName];
						}
					}
				}
			}
		}
	});
});
