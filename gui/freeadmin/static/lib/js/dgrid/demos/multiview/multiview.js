define([
	'require',
	'dgrid/OnDemandGrid',
	'dgrid/Selection',
	'dgrid/Keyboard',
	'dojo/_base/declare',
	'dojo/dom-construct',
	'dojo/on',
	'dstore/RequestMemory',
	'put-selector/put',
	'dojo/text!./resources/description.html',
	'dojo/query'
], function (require, Grid, Selection, Keyboard, declare, domConstruct, on, RequestMemory, put, descriptionHtml) {
	// Render DOM
	var containerNode = put(document.body, 'div');
	var switchNode = put('div.controls', 'Select View: ');
	var tableButton = put(switchNode, 'button[type=button]', 'Table');
	var detailsButton = put(switchNode, 'button[type=button]', 'Details');
	var galleryButton = put(switchNode, 'button[type=button]', 'Gallery');
	var contentNode = put('div.content');
	var gridNode;

	var grid;
	var store;
	var expandoListener;
	var expandedNode;
	var renderers = {
		gallery: function (obj) {
			// function used for renderRow for gallery view (large tiled thumbnails)
			var div = put('div');
			div.innerHTML = '<div class="icon" style="background-image:url(resources/' +
				obj.icon + '-128.png);">&nbsp;</div><div class="name">' + obj.name + '</div>';
			return div;
		},
		details: function (obj) {
			// function used for renderRow for details view (items w/ summary)
			var div = put('div');
			div.innerHTML = '<div class="icon" style="background-image:url(resources/' +
				obj.icon + '-64.png);">&nbsp;</div><div class="name">' +
				obj.name + '</div><div class="summary">' + obj.summary + '</div>';
			return div;
		},
		table: function (obj) {
			var div = put('div.collapsed', Grid.prototype.renderRow.apply(this, arguments));
			put(div, 'div.expando', obj.summary);
			return div;
		}
	};

	function makeViewClickHandler(view) {
		return function () {
			// pause/resume click listener for expando in "table" view
			expandoListener[view === 'table' ? 'resume' : 'pause']();
			// reset expanded node for table view
			expandedNode = null;
			// update renderRow function
			grid.renderRow = renderers[view];
			// update class on grid domNode
			put(grid.domNode, '!table!gallery!details.' + view);
			// only show headers if we're in "table" view
			grid.set('showHeader', view === 'table');
			// force redraw of rows
			grid.refresh();
		};
	}

	put(containerNode, switchNode);

	gridNode = put(contentNode, 'div#grid.table');
	domConstruct.place(descriptionHtml, contentNode);
	put(containerNode, contentNode);

	// Use require.toUrl for portability (looking up via module path)
	store = new RequestMemory({ target: require.toUrl('./data.json') });

	grid = new Grid({
		columns: [
			{
				label: ' ',
				field: 'icon',
				sortable: false,
				formatter: function (icon) {
					return '<div class="icon" style="background-image:url(resources/' +
						icon + '-32.png);">&nbsp;</div>';
				}
			},
			{ label: 'Package', field: 'id' },
			{ label: 'Name', field: 'name' }
		],
		collection: store,
		renderRow: renderers.table
	}, 'grid');

	// store initially-active renderRow as renderer for table view
	renderers.table = grid.renderRow;

	// listen for clicks to trigger expand/collapse in table view mode
	expandoListener = on.pausable(grid.domNode, '.dgrid-row:click', function (event) {
		var node = grid.row(event).element;
		var collapsed = node.className.indexOf('collapsed') >= 0;
		
		// toggle state of node which was clicked
		put(node, (collapsed ? '!' : '.') + 'collapsed');
		
		// if clicked row wasn't expanded, collapse any previously-expanded row
		collapsed && expandedNode && put(expandedNode, '.collapsed');
		
		// if the row clicked was previously expanded, nothing is expanded now
		expandedNode = collapsed ? node : null;
	});

	// switch views when buttons are clicked
	on(tableButton, 'click', makeViewClickHandler('table'));
	on(detailsButton, 'click', makeViewClickHandler('details'));
	on(galleryButton, 'click', makeViewClickHandler('gallery'));
});
