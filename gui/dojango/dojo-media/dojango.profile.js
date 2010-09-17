dependencies = {
	layers: [
		{
			name: "dojo.js",
			dependencies: [
				"dojango.dojango",
				"dojo.parser"
			]
		}
	],
	
	prefixes: [
		[ "dijit", "../dijit" ],
		[ "dojox", "../dojox" ],
		[ "dojango", "../../../dojango" ] // relative to the directory, where the dojo.js source file resides
	]
}

