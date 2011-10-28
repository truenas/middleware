var testResourceRe = /^dijit\/tests\//,
	copyOnly = function(mid){
		var list = {
			"dijit/dijit.profile":1,
			"dijit/package.json":1,
			"dijit/themes/claro/compile":1
		};
		return (mid in list) || (/^dijit\/resources\//.test(mid) && !/\.css$/.test(mid));
	};

var profile = {
	resourceTags:{
		test: function(filename, mid){
			return testResourceRe.test(mid) || mid=="dijit/robot" || mid=="dijit/robotx";
		},

		copyOnly: function(filename, mid){
			return copyOnly(mid);
		},

		amd: function(filename, mid){
			return !testResourceRe.test(mid) && !copyOnly(mid) && /\.js$/.test(filename);
		},

		miniExclude: function(filename, mid){
			return /^dijit\/bench\//.test(mid) || /^dijit\/themes\/themeTest/.test(mid);
		}
	},

	trees:[
		[".", ".", /(\/\.)|(~$)/]
	]
};



