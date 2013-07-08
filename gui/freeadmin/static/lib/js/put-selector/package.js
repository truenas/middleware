var miniExcludes = {
		"put-selector/README.md": 1,
		"put-selector/package": 1
	},
	amdExcludes = {
	},
	copyOnly = {
		"put-selector/node-html": 1
	},
	isJsRe = /\.js$/,
	isTestRe = /\/test\//;

var profile = {
	resourceTags: {
		test: function(filename, mid){
			return isTestRe.test(filename);
		},

		miniExclude: function(filename, mid){
			return isTestRe.test(filename) || mid in miniExcludes;
		},

		amd: function(filename, mid){
			return isJsRe.test(filename) && !(mid in amdExcludes);
		},

		copyOnly: function(filename, mid){
			return mid in copyOnly;
		}
	}
};
