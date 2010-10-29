dojo.provide("dojango.dojango");

dojango.registerModulePath = function(name, absoluteUrl, relativeUrl) {
	/*
	 * This is an extended dojo.registerModulePath function. It sets the right
	 * module path depending if you use a local, a builded local or a remote
	 * xd build of dojo.
	 *
	 * If you don't register a path for a module, dojo assumes to find it in:
	 *
	 *	 ../moduleName
	 *
	 * This is utilized for a local builded version, where your own module will
	 * reside next to dojo/dijit/dojox after it was built.
	 *
	 * An example on how to use an xd build and also loading local files can be found here:
	 * http://jburke.dojotoolkit.org/demos/xdlocal/LocalAndXd.html
	 */
	//if (!(dojo.version.flag.length>0 && dojo.baseUrl.indexOf(dojo.version.flag)>-1)) { // what a dirty hack to recognize a locally builded version
	if (dojo.config.useXDomain) {
		// if we use an xd build located on another host, we have to use the absolute url of the called host
		dojo.registerModulePath(name, absoluteUrl.substring(1)); // because '/' is already set in dojo.baseUrl (this is needed!)
	}
	else if(dojangoConfig.isLocalBuild){
		// normally we don't have to set the module path like this.
		// this is the default module path resolution!
		// we just add it here because of documentation!
		dojo.registerModulePath(name, "../" + name)
	}
	else {
		// relative to the dojo/dojo.js-file
		dojo.registerModulePath(name, relativeUrl);
	}
}

// dojango.registerModulePath("dojango", dojangoConfig.baseUrl + "/dojango", "../../../dojango");

// all required dojango functions must be loaded after the module registration
dojo.require("dojango._base"); // we always include the basic functionality
