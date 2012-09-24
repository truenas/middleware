define([], function(){
	var createdCache, cache = {};
	return {
		load: function(resource, parentRequire, callback, config){
//			resource = parentRequire.toAbsMid(resource); // TODO: Should we be able to normalize the resource? doesn't seem to work in RequireJS, but RequireJS gives us an absolute id here
			cache[resource] = typeof readFile != "undefined" ?
				readFile(parentRequire.toUrl(resource), "utf-8") :
				require.nodeRequire('fs').readFileSync(parentRequire.toUrl(resource), "utf-8"); // how are we supposed to require the 'fs' module in a reliable way? 
			callback({});
		},
		write: function(pluginId, resource, write){
			if(!createdCache){
				createdCache = true;
				write('_css_cache={};');
			}
			write('_css_cache[' + JSON.stringify(resource) + ']=' + JSON.stringify(cache[resource]) + ';');
		}
	}
	
});