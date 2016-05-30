var miniExcludes = {
		'dstore/README.md': 1,
		'dstore/package': 1
	},
	isTestRe = /\/test\//;

var packages = {};
try {
	// retrieve the set of packages for determining which modules to include
	require(['util/build/buildControl'], function (buildControl) {
		packages = buildControl.packages;
	});
} catch (error) {
	console.error('Unable to retrieve packages for determining optional package support in dstore');
}
var profile = {
	resourceTags: {
		test: function (filename, mid) {
			return isTestRe.test(filename);
		},

		miniExclude: function (filename, mid) {
			return /\/(?:tests|demos|docs)\//.test(filename) || mid in miniExcludes;
		},

		amd: function (filename, mid) {
			return /\.js$/.test(filename);
		},

		copyOnly: function (filename, mid) {
			// conditionally omit modules dependent on rql packages
			return (!packages['rql'] && /RqlQuery\.js/.test(filename));
		}
	}
};