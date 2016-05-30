define(['xstyle/core/es6', 'xstyle/core/expression', 'xstyle/core/Definition'],
		function(es6, expression, Definition){
	var react = expression.react;

	function meta(metaName){
		return {
			selfReacting: true,
			apply: function(instance, args, definition){
				var target = args[0];
				var metaDefinition;
				var lastMetaValue;
				var ancestors = [];
				while(target){
					ancestors.push(target);
					target = target.parent;
				}
				return react(function(){
					var keys = [];
					for(var i = 0, l = arguments.length; i < l; i++){
						var object = arguments[i];
						var target = ancestors[i];
						if (object && typeof object === 'object') {
							var metaValue = exports[metaName](object);
							if(metaValue !== undefined){
								if (metaValue !== lastMetaValue) {
									// undepend on last one
									var redefineMeta = true;
									if(metaDefinition){
										metaDefinition.notDependencyOf(definition);
									}
									metaDefinition = new Definition();
									metaDefinition.setSource(metaValue);
								}
								lastMetaValue = metaValue;
								while(keys.length){
									var key = keys.pop();
									metaValue = metaValue[key];
									if(redefineMeta){
										metaDefinition = metaDefinition.property(key);
									}
								}
								if(redefineMeta){
									metaDefinition.dependencyOf(definition);
									// listeners are setup when computed	
									metaDefinition.valueOf();
									//metaDefined = true;
								}
								return metaValue;
							}
						}
						keys.push(target.key);
					}
				}).apply(instance, ancestors, definition);
			}
		};
	}
	var exports = meta('getMeta');
	exports.validate = meta('getErrors');
	exports.createMeta = meta;
	exports.getErrors = function(){
		throw new Error('You must register an error handler');
	};
	exports.getMeta = function(object){
		return object.constructor.properties;
	};
	return exports;
});