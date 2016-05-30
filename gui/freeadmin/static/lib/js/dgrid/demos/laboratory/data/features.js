/**
REQUIRED
	id (Number): unique; sort key (any modules that depend on being loaded after another module should have a higher id)
	label (String): Display value for the feature
	mid (String): absolute mid of the module that provides the feature
	featureType (String): 'grid' or 'column', determining which tab of the UI it appears under

OPTIONAL
	configLevel (String): if 'grid', feature will be applied to grid settings; otherwise feature will be applied to each
		column's settings
	configModule (String): relative (to the 'widgets' folder) mid of the module that provides the configuration UI
	info (String): Tooltip text - longer description of the feature
*/
define([
	'./config',
	'dojo/i18n!../nls/laboratory'
], function (config, i18n) {
	return [
		{
			id: 1.1,
			featureType: 'grid',
			mid: 'dgrid/Grid',
			label: 'Grid',
			configLevel: 'grid',
			configModule: 'configForms/Grid',
			documentationUrl: config.docBaseUrl + 'components/core-components/Grid.md',
			selected: true
		},
		{
			id: 1.2,
			featureType: 'grid',
			mid: 'dgrid/OnDemandGrid',
			label: 'OnDemandGrid',
			configLevel: 'grid',
			configModule: 'configForms/OnDemandGrid',
			documentationUrl: config.docBaseUrl + 'components/core-components/OnDemandList-and-OnDemandGrid.md',
			selected: true
		},
		{
			id: 2,
			featureType: 'grid',
			mid: 'dgrid/Keyboard',
			label: 'Keyboard',
			configLevel: 'grid',
			configModule: 'configForms/Keyboard',
			documentationUrl: config.docBaseUrl + 'components/mixins/Keyboard.md',
			info: i18n.infoKeyboard
		},
		{
			id: 3,
			featureType: 'grid',
			mid: 'dgrid/Selection',
			label: 'Selection',
			configLevel: 'grid',
			configModule: 'configForms/Selection',
			documentationUrl: config.docBaseUrl + 'components/mixins/Selection.md',
			info: i18n.infoSelection
		},
		{
			id: 4,
			featureType: 'grid',
			mid: 'dgrid/CellSelection',
			label: 'CellSelection',
			configLevel: 'grid',
			configModule: 'configForms/CellSelection',
			documentationUrl: config.docBaseUrl + 'components/mixins/CellSelection.md',
			info: i18n.infoCellSelection
		},
		{
			id: 5,
			featureType: 'grid',
			mid: 'dgrid/Tree',
			label: 'Tree',
			configLevel: 'grid',
			configModule: 'configForms/Tree',
			documentationUrl: config.docBaseUrl + 'components/mixins/Tree.md',
			info: i18n.infoTree
		},
		{
			id: 6,
			featureType: 'grid',
			mid: 'dgrid/extensions/Pagination',
			label: 'Pagination',
			configLevel: 'grid',
			configModule: 'configForms/Pagination',
			documentationUrl: config.docBaseUrl + 'components/extensions/Pagination.md',
			info: i18n.infoPagination
		},
		{
			id: 7,
			featureType: 'grid',
			mid: 'dgrid/extensions/DijitRegistry',
			label: 'DijitRegistry',
			documentationUrl: config.docBaseUrl + 'components/extensions/DijitRegistry.md',
			info: i18n.infoDijitRegistry
		},
		{
			id: 8,
			featureType: 'grid',
			mid: 'dgrid/extensions/DnD',
			label: 'DnD',
			configLevel: 'grid',
			documentationUrl: config.docBaseUrl + 'components/extensions/DnD.md',
			info: i18n.infoDnD
		},
		{
			id: 9,
			featureType: 'column',
			mid: 'dgrid/Editor',
			label: 'Editor',
			documentationUrl: config.docBaseUrl + 'components/mixins/Editor.md',
			info: i18n.infoEditor
		},
		{
			id: 10,
			featureType: 'column',
			mid: 'dgrid/extensions/ColumnHider',
			label: 'ColumnHider',
			documentationUrl: config.docBaseUrl + 'components/extensions/ColumnHider.md',
			info: i18n.infoColumnHider
		},
		{
			id: 11,
			featureType: 'column',
			mid: 'dgrid/extensions/ColumnReorder',
			label: 'ColumnReorder',
			documentationUrl: config.docBaseUrl + 'components/extensions/ColumnReorder.md',
			info: i18n.infoColumnReorder
		},
		{
			id: 12,
			featureType: 'column',
			mid: 'dgrid/extensions/ColumnResizer',
			label: 'ColumnResizer',
			configLevel: 'grid',
			configModule: 'configForms/ColumnResizer',
			documentationUrl: config.docBaseUrl + 'components/extensions/ColumnResizer.md',
			info: i18n.infoColumnResizer
		},
		// There's no UI for configuring CompoundColumns or ColumnSet, so just omit them
/*
		{
			id: 13,
			featureType: 'column',
			mid: 'dgrid/extensions/CompoundColumns',
			label: 'CompoundColumns',
			documentationUrl: config.docBaseUrl + 'components/extensions/CompoundColumns.md',
			info: 'TODO: i18n; Define column headers that span multiple grid columns'
		},
		{
			id: 14,
			featureType: 'column',
			mid: 'dgrid/ColumnSet',
			label: 'ColumnSet',
			documentationUrl: config.docBaseUrl + 'components/mixins/ColumnSet.md',
			info: 'TODO: i18n; Define column sets that scroll independently'
		},
*/
		{
			id: 15,
			featureType: 'column',
			mid: 'dgrid/Selector',
			label: 'Selector',
			documentationUrl: config.docBaseUrl + 'components/mixins/Selector.md',
			info: i18n.infoSelector
		}
	];
});
