define([
	'./intern'
], function (intern) {
	intern.useSauceConnect = false;
	
	intern.environments = [
		{ browserName: 'firefox' },
		{ browserName: 'chrome' }
	];

	return intern;
});