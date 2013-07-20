define([
	"doh",
	"dojo/_base/lang",
	"dojo/_base/declare",
	/* _StoreMixin can't really be tested independently from a Grid at the moment,
	 * so we are testing through OnDemandGrid for now. */
	"dgrid/OnDemandGrid",
	"dgrid/ColumnSet",
	"dgrid/test/data/base",
	"dojo/domReady!"
], function(doh, lang, declare, OnDemandGrid, ColumnSet, testStoreMaster){

	// Helper method used to set column set() methods for various grid compositions
	function testSetMethod(){
		var dfd = new doh.Deferred(),
			grid = this.grid;

		var testStore = lang.clone(testStoreMaster); // clone test store so we can make modifications
		grid.set("store", testStore);
		document.body.appendChild(grid.domNode);
		grid.startup();

		var changes = [
				{
					objectId: 0,
					field: "col1",
					newValue: "sleepy",
					expectedSavedValue: "SLEEPY"
				},
				{
					objectId: 1,
					field: "col3",
					newValue: "dopey",
					expectedSavedValue: "DOPEY"
				},
				{
					objectId: 2,
					field: "col4",
					newValue: "rutherford",
					expectedSavedValue: "RUTHERFORD"
				}
			],
			len = changes.length,
			i,
			change;
		
		for(i = 0; i < len; i++){
			change = changes[i];
			grid.updateDirty(change.objectId, change.field, change.newValue);
		}

		grid.save().then(
			dfd.getTestCallback(function(){
				for(var i = 0, change; i < changes.length; i++){
					change = changes[i];
					doh.is(change.expectedSavedValue, testStore.get(change.objectId)[change.field]);
				}
			}),
			lang.hitch(dfd, "errback")
		);

		return dfd;
	}

	// function used for test tear-down
	function destroyGrid(){
		this.grid.destroy();
	}
	
	// the set() method to use for column.set() tests
	function sampleSetMethod(item){
		return item[this.field].toUpperCase();
	}

	doh.register("_StoreMixin", [
		{
			name: "column.set in subRows",
			setUp: function(){
				this.grid = new OnDemandGrid({
					subRows: [
						[
							{ label: 'Column 1', field: 'col1', set: sampleSetMethod },
							{ label: 'Column 2', field: 'col2', sortable: false },
							{ label: 'Column 1', field: 'col1', rowSpan: 2 },
							{ label: 'Column 4', field: 'col4', set: sampleSetMethod }
						],
						[
							{ label: 'Column 3', field: 'col3', colSpan: 2, set: sampleSetMethod },
							{ label: 'Column 5', field: 'col5' }
						]
					]
				});
			},
			runTest: testSetMethod,
			tearDown: destroyGrid
		},
		{
			name: "column.set in columnSets",
			setUp: function(){
				this.grid = new (declare([OnDemandGrid, ColumnSet]))({
					columnSets: [
						[
							[
								{ label: 'Column 1', field: 'col1', set: sampleSetMethod },
								{ label: 'Column 2', field: 'col2', sortable: false }
							],
							[
								{label: 'Column 3', field: 'col3', colSpan: 2, set: sampleSetMethod }
							]
						],
						[
							[
								{ label: 'Column 1', field: 'col1', rowSpan: 2 },
								{ label: 'Column 4', field: 'col4', set: sampleSetMethod }
							],
							[
								{ label: 'Column 5', field: 'col5' }
							]
						]
					]
				});
			},
			runTest: testSetMethod,
			tearDown: destroyGrid
		}
	]);
});
