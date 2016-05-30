define([
	'dgrid/OnDemandGrid',
	'dgrid/Selection',
	'dgrid/Editor',
	'dgrid/extensions/DnD',
	'dojo/_base/declare',
	'dojo/json',
	'dojo/on',
	'dstore/Memory',
	'dstore/Trackable',
	'put-selector/put',
	'dojo/domReady!'
], function (OnDemandGrid, Selection, Editor, DnD, declare, JSON, on, Memory, Trackable, put) {
	// Create DOM
	var container = put('div#container');
	var itemForm = put(container, 'form#itemForm.actionArea.topArea');
	var taskField = put(itemForm, 'input#txtTask[name=task]');
	put(itemForm, 'button[type=submit]', 'Add');

	var listNode = put(container, 'div#list');
	var removeArea = put(container, 'div.actionArea.bottomArea');
	var removeSelectedButton = put(removeArea, 'button[type=button]', 'Remove Selected');
	var removeCompletedButton = put(removeArea, 'button[type=button]', 'Remove Completed');

	put(document.body, container);

	var storeMixins = [ Memory, Trackable ];

	if (window.localStorage) {
		// add functionality for saving/recalling from localStorage
		storeMixins.push(declare(null, {
			STORAGE_KEY: 'dgrid_demo_todo_list',

			constructor: function () {
				var self = this;
				var jsondata = localStorage[this.STORAGE_KEY];

				jsondata && this.setData(JSON.parse(jsondata));

				this.on('add, update, delete', function () {
					localStorage[self.STORAGE_KEY] = JSON.stringify(self.fetchSync());
				});
			}
		}));
	}

	var Store = declare(storeMixins);

	var store = new Store({
		idProperty: 'summary'
	});

	var grid = new (declare([OnDemandGrid, Selection, DnD, Editor]))({
		collection: store,
		columns: {
			completed: {
				editor: 'checkbox',
				label: ' ',
				autoSave: true,
				sortable: false
			},
			summary: {
				field: '_item', // get whole item for use by formatter
				label: 'TODOs',
				sortable: false,
				formatter: function (item) {
					return '<div' + (item.completed ? ' class="completed"' : '') +
						'>' + item.summary + '</div>';
				}
			}
		}
	}, listNode);

	on(itemForm, 'submit', function (event) {
		event.preventDefault();

		// allow overwrite if already exists (by using put, not add)
		store.put({
			completed: false,
			summary: taskField.value
		});
		taskField.value = '';
	});

	on(removeSelectedButton, 'click', function () {
		for (var i in grid.selection) {
			// Each key in the selection map is the id of the item,
			// so we can pass it directly to store.remove.
			store.remove(i);
		}
	});

	on(removeCompletedButton, 'click', function () {
		// query for all completed items and remove them
		store.filter({ completed: true }).fetch().forEach(function (item) {
			store.remove(item[store.idProperty]);
		});
	});

	if (window.localStorage) {
		// add extra button to clear the localStorage key we're using
		var button = put(removeArea, 'button[type=button]',
			'Clear localStorage');

		on(button, 'click', function () {
			localStorage.removeItem(store.STORAGE_KEY);
			// remove all items in grid the quick way (no need to iteratively remove)
			store.setData([]);
			grid.refresh();
		});
	}
});
