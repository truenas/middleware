var miniExcludes = {
		"xstyle/index.html": 1,
		"xstyle/README.md": 1,
		"xstyle/package": 1
	},
	copyOnlyRe = [
		/\/build/, // contents of build folder and build.js
		/\/core\/amdLoader/, // contents of core folder
		/\/core\/put/, // contents of core folder
		/\/xstyle(\.min)?$/ // xstyle.min.*
	],
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
			return /\.js$/.test(filename);
		},
		
		copyOnly: function(filename, mid){
			for(var i = copyOnlyRe.length; i--;){
				if(copyOnlyRe[i].test(mid)){
					return true;
				}
			}
			return false;
		}
	}
};