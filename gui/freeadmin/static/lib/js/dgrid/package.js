var miniExcludes = {
		"dgrid/CHANGES.md": 1,
		"dgrid/LICENSE": 1,
		"dgrid/README.md": 1,
		"dgrid/package": 1
	},
	isTestRe = /\/test\//;

var profile = {
	resourceTags: {
		test: function(filename, mid){
			return isTestRe.test(filename);
		},

		miniExclude: function(filename, mid){
			return /\/(?:test|demos)\//.test(filename) || mid in miniExcludes;
		},

		amd: function(filename, mid){
			return /\.js$/.test(filename);
		}
	}
};