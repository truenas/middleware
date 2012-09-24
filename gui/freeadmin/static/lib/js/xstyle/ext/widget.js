define(['../elemental'], function(elemental){
	function parse(value, callback){
		var Class, prototype;
		if(value.eachProperty){
			var type, props = {/*cssText: value.cssText*/};
			value.eachProperty(function(name, value){
				name = name.replace(/-\w/g, function(dashed){
					return dashed.charAt(1).toUpperCase();
				});
				value = parse(value);
				if(name == "type" && callback){
					type = value;
				}else{
					props[name] = value;
				}
			});
			value = props;
			// load the class, and adjust the property types based on the class prototype  
			if(type){
				require(type.split(/[, ]+/), function(Class, Mixin){
					if(Mixin){
						// more than one, mix them together
						// TODO: This should be Class.extend(arguments.slice(1)), but dojo.declare has a bug in extend that causes it modify the original
						Class = dojo.declare([].slice.call(arguments,0)); // convert the arguments to an array of mixins
					}
					var prototype = Class.prototype;
					for(var name in props){
						var value = props[name];
						if(name in prototype){
							var type = typeof prototype[name];
							if(type == "string" || typeof value != "string"){
							}else if(type == "number"){
								props[name] = +value;
							}else{
								props[name] = eval(value);
							}
						}
					}
					callback(function(element){
						new Class(props, element);
					});
				});
			}
		}else if(value.charAt(0) == "'" || value.charAt(0) == '"'){
			value = eval(value);
		}else if(!isNaN(value)){
			value = +value;
		}
		return value;
	}
	
	function Widget(scope){
		return {
			widget: function(value, rule){
				var modules = [];
				value.replace(/require\s*\(\s*['"]([^'"]*)['"]\s*\)/g, function(t, moduleId){
					modules.push(moduleId);
				});
				require(modules);
				return function(domNode){
					require(modules, function(){
						with(scope){
							var __module = eval(value);
							var prototype = __module.prototype;
							var props = {};
							if(prototype){
								rule.eachProperty(function(t, name, value){
									if(name in prototype){
										var type = typeof prototype[name];
										if(type == "string" || typeof value != "string"){
											props[name] = value;
										}else if(type == "number"){
											props[name] = +value;
										}else{
											props[name] = eval(value);
										}
									}
								});
							}
							__module(props, domNode);
						}
					});
				};
			},
			role: "layout"
		};
	}
	var def = new Widget({});
	Widget.widget = def.widget;
	Widget.role = def.role;
	return {
		onProperty: function(name, value, rule){
			// used for a widget property:
			//	widget: {
			//		type: 'dijit/form/Button';
			//		label: 'Save';
			//	}
			return {
				then: function(callback){
					parse(value, function(renderer){
						elemental.addRenderer(name, value, rule, renderer);
						callback();
					}); 
				}
			}
		}/*,
		onFunction: function(name, propertyName, value){
			// this allows us to create a CSS widget function
			// x-property{
			// 		my-widget: widget(my/Widget);
			//	}
			//	.class{
			//		my-widget: 'settings';
			//	}
			return function(name, propertyValue){
				require([value], function(Class){
					elemental.addRenderer(rule, function(element){
						new Class(parse(propertyValue), element);
					});
				});
			};
		}*/
		
	} 
})