define([], function(){
	var nextId = 0;
	function parse(value, callback, type, rule){
		var Class, prototype;
		if(rule){
			var widgetCssClass = 'x-widget-' + nextId++; 
			// create new rule for the generated elements
			rule.addSheetRule('.' + widgetCssClass, rule.cssText);
			widgetCssClass = ' ' + widgetCssClass; // make it suitable for direct addition to className
		}
		if(value.eachProperty){
			var props = {/*cssText: value.cssText*/};
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
				if(window[type]){
					classLoaded(window[type]);
				}
				require(typeof type == 'string' ? type.split(/\s*,\s*/) : type, classLoaded); 
				function classLoaded(Class, Mixin){
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
						var widget = new Class(props, element);
						widget.domNode.className += widgetCssClass;
					});
				}
			}else if(callback){
				console.error("No type defined for widget");
			}
		}else if(typeof value == 'object'){
			// an array or object
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
		put: function(value, rule, name){
			// used for a widget property:
			//	widget: {
			//		type: 'dijit/form/Button';
			//		label: 'Save';
			//	}
			return {
				then: function(callback){
					parse(value[0].eachProperty ? value[0] : rule, function(renderer){
						rule.elements(renderer);
						callback();
					}, typeof value == "string" && value, rule); 
				}
			}
		},
		parse: parse
		/*,
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
					xstyle.addRenderer(rule, function(element){
						new Class(parse(propertyValue), element);
					});
				});
			};
		}*/
		
	} 
})