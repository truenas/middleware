define([
	"intern!tdd",
	"intern/chai!assert",
	"dojo/_base/declare",
	"dgrid/Grid",
	"dgrid/extensions/CompoundColumns"
], function(test, assert, declare, Grid, CompoundColumns){
	var CompoundColumnGrid = declare([Grid, CompoundColumns]),
		data = [],
		grid;

	// Generate data to be used for all tests
	for(var itemIndex = 0; itemIndex < 12; itemIndex++){
		var item = { id: itemIndex };
		for(var propIndex = 0; propIndex < 10; propIndex++){
			item["data" + propIndex] = "Value " + itemIndex + ":" + propIndex;
		}
		data.push(item);
	}

	function createGrid(columns, hideHeader){
		grid = new CompoundColumnGrid({
			columns: columns,
			showHeader: !hideHeader
		});
		document.body.appendChild(grid.domNode);
		grid.startup();
		grid.renderArray(data);
	}

	test.suite("CompoundColumns", function(){
		test.suite("cell method", function(){
			test.afterEach(function(){
				grid.destroy();
			});

			test.test("simple grid", function(){
				createGrid({
					data0: "Data 0",
					data1: "Data 1",
					data2: "Data 2",
					data3: "Data 3",
					data4: "Data 4"
				}, true);

				assert.strictEqual(grid.cell(0, 0).element.innerHTML, "Value 0:0");
				assert.strictEqual(grid.cell(0, 4).element.innerHTML, "Value 0:4");
				assert.strictEqual(grid.cell(11, 0).element.innerHTML, "Value 11:0");
				assert.strictEqual(grid.cell(11, 4).element.innerHTML, "Value 11:4");
				assert.isUndefined(grid.cell(0, 5).element);
				assert.isUndefined(grid.cell(12, 0).element);
			});

			test.test("simple grid with column ids", function(){
				createGrid({
					data0: { label: "Data 0", id: "myData0" },
					data1: { label: "Data 1", id: "myData1" },
					data2: { label: "Data 2", id: "myData2" },
					data3: { label: "Data 3", id: "myData3" },
					data4: { label: "Data 4", id: "myData4" }
				}, true);

				assert.strictEqual(grid.cell(0, "myData0").element.innerHTML, "Value 0:0");
				assert.strictEqual(grid.cell(0, "myData4").element.innerHTML, "Value 0:4");
				assert.strictEqual(grid.cell(11, "myData0").element.innerHTML, "Value 11:0");
				assert.strictEqual(grid.cell(11, "myData4").element.innerHTML, "Value 11:4");
				assert.isUndefined(grid.cell(0, "myData5").element);
				assert.isUndefined(grid.cell(12, "myData0").element);

				assert.isUndefined(grid.cell(0, 0).element);
			});

			test.test("grid with children", function(){
				createGrid([
					{ field: "data0", label: "Data 0" },
					{
						label: "Compound 1",
						children: [
							{ field: "data1", label: "Data 1" },
							{ field: "data2", label: "Data 2" }
						]
					},
					{ field: "data3", label: "Data 3" },
					{
						label: "Compound 2",
						children: [
							{ field: "data4", label: "Data 4" },
							{ field: "data5", label: "Data 5" }
						]
					}
				]);

				assert.strictEqual(grid.cell(0, 0).element.innerHTML, "Value 0:0");
				assert.strictEqual(grid.cell(0, 1).element.innerHTML, "Value 0:1");
				assert.strictEqual(grid.cell(0, 2).element.innerHTML, "Value 0:2");
				assert.strictEqual(grid.cell(0, 5).element.innerHTML, "Value 0:5");
				assert.strictEqual(grid.cell(11, 0).element.innerHTML, "Value 11:0");
				assert.strictEqual(grid.cell(11, 1).element.innerHTML, "Value 11:1");
				assert.strictEqual(grid.cell(11, 2).element.innerHTML, "Value 11:2");
				assert.strictEqual(grid.cell(11, 5).element.innerHTML, "Value 11:5");

				assert.isUndefined(grid.cell(0, 6).element);
				assert.isUndefined(grid.cell(12, 0).element);
			});

			test.test("grid with children and children ids", function(){
				createGrid([
					{ field: "data0", label: "Data 0" },
					{
						label: "Compound 1",
						children: [
							{ field: "data1", label: "Data 1", id: "myData1"},
							{ field: "data2", label: "Data 2", id: "myData2" }
						]
					},
					{ field: "data3", label: "Data 3" },
					{
						label: "Compound 2",
						children: [
							{ field: "data4", label: "Data 4", id: "myData4" },
							{ field: "data5", label: "Data 5", id: "myData5" }
						]
					}
				]);

				assert.strictEqual(grid.cell(0, 0).element.innerHTML, "Value 0:0");
				assert.strictEqual(grid.cell(0, 3).element.innerHTML, "Value 0:3");
				assert.strictEqual(grid.cell(0, "myData1").element.innerHTML, "Value 0:1");
				assert.strictEqual(grid.cell(0, "myData2").element.innerHTML, "Value 0:2");
				assert.strictEqual(grid.cell(0, "myData5").element.innerHTML, "Value 0:5");
				assert.strictEqual(grid.cell(11, 0).element.innerHTML, "Value 11:0");
				assert.strictEqual(grid.cell(11, 3).element.innerHTML, "Value 11:3");
				assert.strictEqual(grid.cell(11, "myData1").element.innerHTML, "Value 11:1");
				assert.strictEqual(grid.cell(11, "myData2").element.innerHTML, "Value 11:2");
				assert.strictEqual(grid.cell(11, "myData5").element.innerHTML, "Value 11:5");

				assert.strictEqual(grid.cell(0, "0-1-myData1").element.innerHTML, "Value 0:1");
				assert.strictEqual(grid.cell(0, "0-1-myData2").element.innerHTML, "Value 0:2");
				assert.strictEqual(grid.cell(0, "0-4-myData5").element.innerHTML, "Value 0:5");
				assert.strictEqual(grid.cell(11, "0-1-myData1").element.innerHTML, "Value 11:1");
				assert.strictEqual(grid.cell(11, "0-1-myData2").element.innerHTML, "Value 11:2");
				assert.strictEqual(grid.cell(11, "0-4-myData5").element.innerHTML, "Value 11:5");

				assert.strictEqual(grid.cell(0, "1-myData1").element.innerHTML, "Value 0:1");
				assert.strictEqual(grid.cell(0, "1-myData2").element.innerHTML, "Value 0:2");
				assert.strictEqual(grid.cell(0, "4-myData5").element.innerHTML, "Value 0:5");
				assert.strictEqual(grid.cell(11, "1-myData1").element.innerHTML, "Value 11:1");
				assert.strictEqual(grid.cell(11, "1-myData2").element.innerHTML, "Value 11:2");
				assert.strictEqual(grid.cell(11, "4-myData5").element.innerHTML, "Value 11:5");
			});

			test.test("grid with children and ids", function(){
				createGrid([
					{ field: "data0", label: "Data 0" },
					{
						label: "Compound 1",
						id: "compound1",
						children: [
							{ field: "data1", label: "Data 1", id: "myData1"},
							{ field: "data2", label: "Data 2", id: "myData2" }
						]
					},
					{ field: "data3", label: "Data 3" },
					{
						label: "Compound 2",
						id: "compound2",
						children: [
							{ field: "data4", label: "Data 4", id: "myData4" },
							{ field: "data5", label: "Data 5", id: "myData5" }
						]
					}
				]);

				assert.strictEqual(grid.cell(0, 0).element.innerHTML, "Value 0:0");
				assert.strictEqual(grid.cell(0, 3).element.innerHTML, "Value 0:3");
				assert.strictEqual(grid.cell(0, "myData1").element.innerHTML, "Value 0:1");
				assert.strictEqual(grid.cell(0, "myData2").element.innerHTML, "Value 0:2");
				assert.strictEqual(grid.cell(0, "myData5").element.innerHTML, "Value 0:5");
				assert.strictEqual(grid.cell(11, 0).element.innerHTML, "Value 11:0");
				assert.strictEqual(grid.cell(11, 3).element.innerHTML, "Value 11:3");
				assert.strictEqual(grid.cell(11, "myData1").element.innerHTML, "Value 11:1");
				assert.strictEqual(grid.cell(11, "myData2").element.innerHTML, "Value 11:2");
				assert.strictEqual(grid.cell(11, "myData5").element.innerHTML, "Value 11:5");

				assert.strictEqual(grid.cell(0, "compound1-myData1").element.innerHTML, "Value 0:1");
				assert.strictEqual(grid.cell(0, "compound1-myData2").element.innerHTML, "Value 0:2");
				assert.strictEqual(grid.cell(0, "compound2-myData5").element.innerHTML, "Value 0:5");
				assert.strictEqual(grid.cell(11, "compound1-myData1").element.innerHTML, "Value 11:1");
				assert.strictEqual(grid.cell(11, "compound1-myData2").element.innerHTML, "Value 11:2");
				assert.strictEqual(grid.cell(11, "compound2-myData5").element.innerHTML, "Value 11:5");
			});

			test.test("grid with nested children and ids", function(){
				createGrid([
					{ field: "data0", label: "Data 0" },
					{
						label: "Compound 1",
						id: "compound1",
						children: [
							{
								label: "Nested Compound 1",
								id: "nested1",
								children: [
									{ field: "data1", label: "Data 1", id: "myData1" },
									{ field: "data9", label: "Data 9", id: "myData9" }
								]
							},
							{ field: "data2", label: "Data 2", id: "myData2" }
						]
					},
					{ field: "data3", label: "Data 3" },
					{
						label: "Compound 2",
						id: "compound2",
						children: [
							{ field: "data4", label: "Data 4", id: "myData4" },
							{
								label: "Nested Compound 2",
								id: "nested2",
								children: [
									{ field: "data5", label: "Data 5", id: "myData5" },
									{ field: "data8", label: "Data 8", id: "myData8" }
								]
							}
						]
					}
				]);

				assert.strictEqual(grid.cell(0, "myData1").element.innerHTML, "Value 0:1");
				assert.strictEqual(grid.cell(0, "myData2").element.innerHTML, "Value 0:2");
				assert.strictEqual(grid.cell(0, "myData9").element.innerHTML, "Value 0:9");
				assert.strictEqual(grid.cell(0, "myData4").element.innerHTML, "Value 0:4");
				assert.strictEqual(grid.cell(0, "myData5").element.innerHTML, "Value 0:5");
				assert.strictEqual(grid.cell(0, "myData8").element.innerHTML, "Value 0:8");
				assert.strictEqual(grid.cell(11, "myData1").element.innerHTML, "Value 11:1");
				assert.strictEqual(grid.cell(11, "myData2").element.innerHTML, "Value 11:2");
				assert.strictEqual(grid.cell(11, "myData9").element.innerHTML, "Value 11:9");
				assert.strictEqual(grid.cell(11, "myData4").element.innerHTML, "Value 11:4");
				assert.strictEqual(grid.cell(11, "myData5").element.innerHTML, "Value 11:5");
				assert.strictEqual(grid.cell(11, "myData8").element.innerHTML, "Value 11:8");

				assert.strictEqual(grid.cell(0, "nested1-myData1").element.innerHTML, "Value 0:1");
				assert.strictEqual(grid.cell(0, "nested1-myData9").element.innerHTML, "Value 0:9");
				assert.strictEqual(grid.cell(0, "nested2-myData5").element.innerHTML, "Value 0:5");
				assert.strictEqual(grid.cell(0, "nested2-myData8").element.innerHTML, "Value 0:8");
				assert.strictEqual(grid.cell(11, "nested1-myData1").element.innerHTML, "Value 11:1");
				assert.strictEqual(grid.cell(11, "nested1-myData9").element.innerHTML, "Value 11:9");
				assert.strictEqual(grid.cell(11, "nested2-myData5").element.innerHTML, "Value 11:5");
				assert.strictEqual(grid.cell(11, "nested2-myData8").element.innerHTML, "Value 11:8");

				assert.strictEqual(grid.cell(0, "compound1-nested1-myData1").element.innerHTML, "Value 0:1");
				assert.strictEqual(grid.cell(0, "compound1-nested1-myData9").element.innerHTML, "Value 0:9");
				assert.strictEqual(grid.cell(0, "compound2-nested2-myData5").element.innerHTML, "Value 0:5");
				assert.strictEqual(grid.cell(0, "compound2-nested2-myData8").element.innerHTML, "Value 0:8");
				assert.strictEqual(grid.cell(11, "compound1-nested1-myData1").element.innerHTML, "Value 11:1");
				assert.strictEqual(grid.cell(11, "compound1-nested1-myData9").element.innerHTML, "Value 11:9");
				assert.strictEqual(grid.cell(11, "compound2-nested2-myData5").element.innerHTML, "Value 11:5");
				assert.strictEqual(grid.cell(11, "compound2-nested2-myData8").element.innerHTML, "Value 11:8");
			});

			test.test("grid with nested children and ids hiding all headers", function(){
				createGrid([
					{ field: "data0", label: "Data 0" },
					{
						label: "Compound 1",
						id: "compound1",
						children: [
							{
								label: "Nested Compound 1",
								id: "nested1",
								children: [
									{ field: "data1", label: "Data 1", id: "myData1" },
									{ field: "data9", label: "Data 9", id: "myData9" }
								]
							},
							{ field: "data2", label: "Data 2", id: "myData2" }
						]
					},
					{ field: "data3", label: "Data 3" },
					{
						label: "Compound 2",
						id: "compound2",
						children: [
							{ field: "data4", label: "Data 4", id: "myData4" },
							{
								label: "Nested Compound 2",
								id: "nested2",
								children: [
									{ field: "data5", label: "Data 5", id: "myData5" },
									{ field: "data8", label: "Data 8", id: "myData8" }
								]
							}
						]
					}
				], true);

				assert.strictEqual(grid.cell(0, "myData1").element.innerHTML, "Value 0:1");
				assert.strictEqual(grid.cell(0, "myData2").element.innerHTML, "Value 0:2");
				assert.strictEqual(grid.cell(0, "myData9").element.innerHTML, "Value 0:9");
				assert.strictEqual(grid.cell(0, "myData4").element.innerHTML, "Value 0:4");
				assert.strictEqual(grid.cell(0, "myData5").element.innerHTML, "Value 0:5");
				assert.strictEqual(grid.cell(0, "myData8").element.innerHTML, "Value 0:8");
				assert.strictEqual(grid.cell(11, "myData1").element.innerHTML, "Value 11:1");
				assert.strictEqual(grid.cell(11, "myData2").element.innerHTML, "Value 11:2");
				assert.strictEqual(grid.cell(11, "myData9").element.innerHTML, "Value 11:9");
				assert.strictEqual(grid.cell(11, "myData4").element.innerHTML, "Value 11:4");
				assert.strictEqual(grid.cell(11, "myData5").element.innerHTML, "Value 11:5");
				assert.strictEqual(grid.cell(11, "myData8").element.innerHTML, "Value 11:8");

				assert.strictEqual(grid.cell(0, "nested1-myData1").element.innerHTML, "Value 0:1");
				assert.strictEqual(grid.cell(0, "nested1-myData9").element.innerHTML, "Value 0:9");
				assert.strictEqual(grid.cell(0, "nested2-myData5").element.innerHTML, "Value 0:5");
				assert.strictEqual(grid.cell(0, "nested2-myData8").element.innerHTML, "Value 0:8");
				assert.strictEqual(grid.cell(11, "nested1-myData1").element.innerHTML, "Value 11:1");
				assert.strictEqual(grid.cell(11, "nested1-myData9").element.innerHTML, "Value 11:9");
				assert.strictEqual(grid.cell(11, "nested2-myData5").element.innerHTML, "Value 11:5");
				assert.strictEqual(grid.cell(11, "nested2-myData8").element.innerHTML, "Value 11:8");

				assert.strictEqual(grid.cell(0, "compound1-nested1-myData1").element.innerHTML, "Value 0:1");
				assert.strictEqual(grid.cell(0, "compound1-nested1-myData9").element.innerHTML, "Value 0:9");
				assert.strictEqual(grid.cell(0, "compound2-nested2-myData5").element.innerHTML, "Value 0:5");
				assert.strictEqual(grid.cell(0, "compound2-nested2-myData8").element.innerHTML, "Value 0:8");
				assert.strictEqual(grid.cell(11, "compound1-nested1-myData1").element.innerHTML, "Value 11:1");
				assert.strictEqual(grid.cell(11, "compound1-nested1-myData9").element.innerHTML, "Value 11:9");
				assert.strictEqual(grid.cell(11, "compound2-nested2-myData5").element.innerHTML, "Value 11:5");
				assert.strictEqual(grid.cell(11, "compound2-nested2-myData8").element.innerHTML, "Value 11:8");
			});

			test.test("grid with nested children and ids hiding child headers", function(){
				createGrid([
					{ field: "data0", label: "Data 0" },
					{
						label: "Compound 1",
						id: "compound1",
						children: [
							{
								label: "Nested Compound 1",
								id: "nested1",
								showChildHeaders: false,
								children: [
									{ field: "data1", label: "Data 1", id: "myData1" },
									{ field: "data9", label: "Data 9", id: "myData9" }
								]
							},
							{ field: "data2", label: "Data 2", id: "myData2" }
						]
					},
					{ field: "data3", label: "Data 3" },
					{
						label: "Compound 2",
						id: "compound2",
						children: [
							{ field: "data4", label: "Data 4", id: "myData4" },
							{
								label: "Nested Compound 2",
								id: "nested2",
								showChildHeaders: false,
								children: [
									{ field: "data5", label: "Data 5", id: "myData5" },
									{ field: "data8", label: "Data 8", id: "myData8" }
								]
							}
						]
					}
				]);

				assert.strictEqual(grid.cell(0, "myData1").element.innerHTML, "Value 0:1");
				assert.strictEqual(grid.cell(0, "myData2").element.innerHTML, "Value 0:2");
				assert.strictEqual(grid.cell(0, "myData9").element.innerHTML, "Value 0:9");
				assert.strictEqual(grid.cell(0, "myData4").element.innerHTML, "Value 0:4");
				assert.strictEqual(grid.cell(0, "myData5").element.innerHTML, "Value 0:5");
				assert.strictEqual(grid.cell(0, "myData8").element.innerHTML, "Value 0:8");
				assert.strictEqual(grid.cell(11, "myData1").element.innerHTML, "Value 11:1");
				assert.strictEqual(grid.cell(11, "myData2").element.innerHTML, "Value 11:2");
				assert.strictEqual(grid.cell(11, "myData9").element.innerHTML, "Value 11:9");
				assert.strictEqual(grid.cell(11, "myData4").element.innerHTML, "Value 11:4");
				assert.strictEqual(grid.cell(11, "myData5").element.innerHTML, "Value 11:5");
				assert.strictEqual(grid.cell(11, "myData8").element.innerHTML, "Value 11:8");

				assert.strictEqual(grid.cell(0, "nested1-myData1").element.innerHTML, "Value 0:1");
				assert.strictEqual(grid.cell(0, "nested1-myData9").element.innerHTML, "Value 0:9");
				assert.strictEqual(grid.cell(0, "nested2-myData5").element.innerHTML, "Value 0:5");
				assert.strictEqual(grid.cell(0, "nested2-myData8").element.innerHTML, "Value 0:8");
				assert.strictEqual(grid.cell(11, "nested1-myData1").element.innerHTML, "Value 11:1");
				assert.strictEqual(grid.cell(11, "nested1-myData9").element.innerHTML, "Value 11:9");
				assert.strictEqual(grid.cell(11, "nested2-myData5").element.innerHTML, "Value 11:5");
				assert.strictEqual(grid.cell(11, "nested2-myData8").element.innerHTML, "Value 11:8");

				assert.strictEqual(grid.cell(0, "compound1-nested1-myData1").element.innerHTML, "Value 0:1");
				assert.strictEqual(grid.cell(0, "compound1-nested1-myData9").element.innerHTML, "Value 0:9");
				assert.strictEqual(grid.cell(0, "compound2-nested2-myData5").element.innerHTML, "Value 0:5");
				assert.strictEqual(grid.cell(0, "compound2-nested2-myData8").element.innerHTML, "Value 0:8");
				assert.strictEqual(grid.cell(11, "compound1-nested1-myData1").element.innerHTML, "Value 11:1");
				assert.strictEqual(grid.cell(11, "compound1-nested1-myData9").element.innerHTML, "Value 11:9");
				assert.strictEqual(grid.cell(11, "compound2-nested2-myData5").element.innerHTML, "Value 11:5");
				assert.strictEqual(grid.cell(11, "compound2-nested2-myData8").element.innerHTML, "Value 11:8");
			});
		});

		test.suite("column method", function(){
			test.afterEach(function(){
				grid.destroy();
			});

			test.test("simple grid", function(){
				createGrid({
					data0: "Data 0",
					data1: "Data 1",
					data2: "Data 2",
					data3: "Data 3",
					data4: "Data 4"
				}, true);

				assert.strictEqual(grid.column(0).label, "Data 0");
				assert.strictEqual(grid.column(4).label, "Data 4");
				assert.isUndefined(grid.column(5));
			});

			test.test("simple grid with column ids", function(){
				createGrid({
					data0: { label: "Data 0", id: "myData0" },
					data1: { label: "Data 1", id: "myData1" },
					data2: { label: "Data 2", id: "myData2" },
					data3: { label: "Data 3", id: "myData3" },
					data4: { label: "Data 4", id: "myData4" }
				}, true);

				assert.strictEqual(grid.column("myData0").label, "Data 0");
				assert.strictEqual(grid.column("myData4").label, "Data 4");
				assert.isUndefined(grid.column("myData5"));
				assert.isUndefined(grid.column(0));
			});

			test.test("grid with children", function(){
				createGrid([
					{ field: "data0", label: "Data 0" },
					{
						label: "Compound 1",
						children: [
							{ field: "data1", label: "Data 1" },
							{ field: "data2", label: "Data 2" }
						]
					},
					{ field: "data3", label: "Data 3" },
					{
						label: "Compound 2",
						children: [
							{ field: "data4", label: "Data 4" },
							{ field: "data5", label: "Data 5" }
						]
					}
				]);

				assert.strictEqual(grid.column(0).label, "Data 0");
				assert.strictEqual(grid.column(1).label, "Data 1");
				assert.strictEqual(grid.column(2).label, "Data 2");
				assert.strictEqual(grid.column(5).label, "Data 5");
				assert.isUndefined(grid.column(6));
			});

			test.test("grid with children and children ids", function(){
				createGrid([
					{ field: "data0", label: "Data 0" },
					{
						label: "Compound 1",
						children: [
							{ field: "data1", label: "Data 1", id: "myData1"},
							{ field: "data2", label: "Data 2", id: "myData2" }
						]
					},
					{ field: "data3", label: "Data 3" },
					{
						label: "Compound 2",
						children: [
							{ field: "data4", label: "Data 4", id: "myData4" },
							{ field: "data5", label: "Data 5", id: "myData5" }
						]
					}
				]);

				assert.strictEqual(grid.column(0).label, "Data 0");
				assert.strictEqual(grid.column(3).label, "Data 3");
				assert.strictEqual(grid.column("myData1").label, "Data 1");
				assert.strictEqual(grid.column("myData2").label, "Data 2");
				assert.strictEqual(grid.column("myData5").label, "Data 5");

				assert.strictEqual(grid.column("0-1-myData1").label, "Data 1");
				assert.strictEqual(grid.column("0-1-myData2").label, "Data 2");
				assert.strictEqual(grid.column("0-4-myData5").label, "Data 5");

				assert.strictEqual(grid.column("1-myData1").label, "Data 1");
				assert.strictEqual(grid.column("1-myData2").label, "Data 2");
				assert.strictEqual(grid.column("4-myData5").label, "Data 5");
			});

			test.test("grid with children and ids", function(){
				createGrid([
					{ field: "data0", label: "Data 0" },
					{
						label: "Compound 1",
						id: "compound1",
						children: [
							{ field: "data1", label: "Data 1", id: "myData1"},
							{ field: "data2", label: "Data 2", id: "myData2" }
						]
					},
					{ field: "data3", label: "Data 3" },
					{
						label: "Compound 2",
						id: "compound2",
						children: [
							{ field: "data4", label: "Data 4", id: "myData4" },
							{ field: "data5", label: "Data 5", id: "myData5" }
						]
					}
				]);

				assert.strictEqual(grid.column(0).label, "Data 0");
				assert.strictEqual(grid.column(3).label, "Data 3");
				assert.strictEqual(grid.column("myData1").label, "Data 1");
				assert.strictEqual(grid.column("myData2").label, "Data 2");
				assert.strictEqual(grid.column("myData5").label, "Data 5");

				assert.strictEqual(grid.column("compound1-myData1").label, "Data 1");
				assert.strictEqual(grid.column("compound1-myData2").label, "Data 2");
				assert.strictEqual(grid.column("compound2-myData5").label, "Data 5");
			});

			test.test("grid with nested children and ids", function(){
				createGrid([
					{ field: "data0", label: "Data 0" },
					{
						label: "Compound 1",
						id: "compound1",
						children: [
							{
								label: "Nested Compound 1",
								id: "nested1",
								children: [
									{ field: "data1", label: "Data 1", id: "myData1" },
									{ field: "data9", label: "Data 9", id: "myData9" }
								]
							},
							{ field: "data2", label: "Data 2", id: "myData2" }
						]
					},
					{ field: "data3", label: "Data 3" },
					{
						label: "Compound 2",
						id: "compound2",
						children: [
							{ field: "data4", label: "Data 4", id: "myData4" },
							{
								label: "Nested Compound 2",
								id: "nested2",
								children: [
									{ field: "data5", label: "Data 5", id: "myData5" },
									{ field: "data8", label: "Data 8", id: "myData8" }
								]
							}
						]
					}
				]);

				assert.strictEqual(grid.column("myData1").label, "Data 1");
				assert.strictEqual(grid.column("myData2").label, "Data 2");
				assert.strictEqual(grid.column("myData9").label, "Data 9");
				assert.strictEqual(grid.column("myData4").label, "Data 4");
				assert.strictEqual(grid.column("myData5").label, "Data 5");
				assert.strictEqual(grid.column("myData8").label, "Data 8");

				assert.strictEqual(grid.column("nested1-myData1").label, "Data 1");
				assert.strictEqual(grid.column("nested1-myData9").label, "Data 9");
				assert.strictEqual(grid.column("nested2-myData5").label, "Data 5");
				assert.strictEqual(grid.column("nested2-myData8").label, "Data 8");

				assert.strictEqual(grid.column("compound1-nested1-myData1").label, "Data 1");
				assert.strictEqual(grid.column("compound1-nested1-myData9").label, "Data 9");
				assert.strictEqual(grid.column("compound2-nested2-myData5").label, "Data 5");
				assert.strictEqual(grid.column("compound2-nested2-myData8").label, "Data 8");
			});

			test.test("grid with nested children and ids hiding all headers", function(){
				createGrid([
					{ field: "data0", label: "Data 0" },
					{
						label: "Compound 1",
						id: "compound1",
						children: [
							{
								label: "Nested Compound 1",
								id: "nested1",
								children: [
									{ field: "data1", label: "Data 1", id: "myData1" },
									{ field: "data9", label: "Data 9", id: "myData9" }
								]
							},
							{ field: "data2", label: "Data 2", id: "myData2" }
						]
					},
					{ field: "data3", label: "Data 3" },
					{
						label: "Compound 2",
						id: "compound2",
						children: [
							{ field: "data4", label: "Data 4", id: "myData4" },
							{
								label: "Nested Compound 2",
								id: "nested2",
								children: [
									{ field: "data5", label: "Data 5", id: "myData5" },
									{ field: "data8", label: "Data 8", id: "myData8" }
								]
							}
						]
					}
				], true);

				assert.strictEqual(grid.column("myData1").label, "Data 1");
				assert.strictEqual(grid.column("myData2").label, "Data 2");
				assert.strictEqual(grid.column("myData9").label, "Data 9");
				assert.strictEqual(grid.column("myData4").label, "Data 4");
				assert.strictEqual(grid.column("myData5").label, "Data 5");
				assert.strictEqual(grid.column("myData8").label, "Data 8");

				assert.strictEqual(grid.column("nested1-myData1").label, "Data 1");
				assert.strictEqual(grid.column("nested1-myData9").label, "Data 9");
				assert.strictEqual(grid.column("nested2-myData5").label, "Data 5");
				assert.strictEqual(grid.column("nested2-myData8").label, "Data 8");

				assert.strictEqual(grid.column("compound1-nested1-myData1").label, "Data 1");
				assert.strictEqual(grid.column("compound1-nested1-myData9").label, "Data 9");
				assert.strictEqual(grid.column("compound2-nested2-myData5").label, "Data 5");
				assert.strictEqual(grid.column("compound2-nested2-myData8").label, "Data 8");
			});

			test.test("grid with nested children and ids hiding child headers", function(){
				createGrid([
					{ field: "data0", label: "Data 0" },
					{
						label: "Compound 1",
						id: "compound1",
						children: [
							{
								label: "Nested Compound 1",
								id: "nested1",
								showChildHeaders: false,
								children: [
									{ field: "data1", label: "Data 1", id: "myData1" },
									{ field: "data9", label: "Data 9", id: "myData9" }
								]
							},
							{ field: "data2", label: "Data 2", id: "myData2" }
						]
					},
					{ field: "data3", label: "Data 3" },
					{
						label: "Compound 2",
						id: "compound2",
						children: [
							{ field: "data4", label: "Data 4", id: "myData4" },
							{
								label: "Nested Compound 2",
								id: "nested2",
								showChildHeaders: false,
								children: [
									{ field: "data5", label: "Data 5", id: "myData5" },
									{ field: "data8", label: "Data 8", id: "myData8" }
								]
							}
						]
					}
				]);

				assert.strictEqual(grid.column("myData1").label, "Data 1");
				assert.strictEqual(grid.column("myData2").label, "Data 2");
				assert.strictEqual(grid.column("myData9").label, "Data 9");
				assert.strictEqual(grid.column("myData4").label, "Data 4");
				assert.strictEqual(grid.column("myData5").label, "Data 5");
				assert.strictEqual(grid.column("myData8").label, "Data 8");

				assert.strictEqual(grid.column("nested1-myData1").label, "Data 1");
				assert.strictEqual(grid.column("nested1-myData9").label, "Data 9");
				assert.strictEqual(grid.column("nested2-myData5").label, "Data 5");
				assert.strictEqual(grid.column("nested2-myData8").label, "Data 8");

				assert.strictEqual(grid.column("compound1-nested1-myData1").label, "Data 1");
				assert.strictEqual(grid.column("compound1-nested1-myData9").label, "Data 9");
				assert.strictEqual(grid.column("compound2-nested2-myData5").label, "Data 5");
				assert.strictEqual(grid.column("compound2-nested2-myData8").label, "Data 8");
			});
		});
	});
});