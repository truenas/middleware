require([
	${dependencies}
], function (${callbackParams}) {
	${dataDeclaration}

	// Instantiate grid
	var grid = new (declare([${gridModules}]))(${gridOptions}, 'grid');

	grid.startup();${gridRender}${dataCreation}
});
