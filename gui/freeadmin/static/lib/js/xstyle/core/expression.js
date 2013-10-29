define("xstyle/core/expression", ["xstyle/core/utils"], function(utils){
	// handles the creation of reactive expressions
	var jsKeywords = {
		'true': true, 'false': false, 'null': 'null', 'typeof': 'typeof', or: '||', and: '&&'
	};
	var nextId = 1;
	function get(target, path, callback){
		return utils.when(target, function(target){
			var name = path[0];
			if(!target){
				return callback(name || target);
			}
			if(name && target.get){
				return get(target.get(name), path.slice(1), callback);
			}
			if(target.receive){
				return target.receive(name ? function(value){
					get(value, path, callback);
				} : callback);
			}
			if(name){
				return get(target[name], path.slice(1), callback);
			}
			return callback(target);
		});
	}
	function set(target, path, value){
		get(target, path.slice(0, path.length - 1), function(target){
			var property = path[path.length - 1];
			target.set ?
				target.set(property, value) :
				target[property] = value;
		});
	}
	return function(rule, name, value){
		// evaluate a binding
		var binding = rule["var-expr-" + name];
		if(variables){
			return binding;
		}
		var variables = [], isElementDependent;
		variables.id = nextId++;
		var target, parameters = [], id = 0, callbacks = [],
			attributeParts, expression = value.join ? value.join("") : value.toString(),
			simpleExpression = expression.match(/^[\w_$\/\.-]*$/); 
		// Do the parsing and function creation just once, and adapt the dependencies for the element at creation time
		// deal with an array, converting strings to JS-eval'able strings
			// find all the variables in the expression
		expression = expression.replace(/("[^\"]*")|([\w_$\.\/-]+)/g, function(t, string, variable){
			if(variable){
				if(jsKeywords.hasOwnProperty(variable)){
					return jsKeywords[variable];
				}
				// for each reference, we break apart into variable reference and property references after each dot				
				attributeParts = variable.split('/');
				var parameterName = attributeParts.join('_').replace(/-/g,'_');
				parameters.push(parameterName);
				variables.push(attributeParts);
				// first find the rule that is being referenced
				var firstReference = attributeParts[0];
				var target = rule.getDefinition(firstReference);
				if(typeof target == 'string' || target instanceof Array){
					target = evaluateExpression(rule, firstReference, target);
				}else if(!target){
					throw new Error('Could not find reference "' + firstReference + '"');					
				}
				if(target.forElement){
					isElementDependent = true;
				}
				attributeParts[0] = target;
				// we will reference the variable a function argument in the function we will create
				return parameterName;
			}
			return t;
		})
	
		if(simpleExpression){
			// a direct reversible reference
			// no forward reactive needed
			if(name){
				// create the reverse function
				var reversal = function(element, name, value){
					utils.when(findAttributeInAncestors(element, attributeParts[0], attributeParts[1]), function(target){
						for(var i = 2; i < attributeParts.length -1; i++){
							var name = attributeParts[i];
							target = target.get ?
								target.get(name) :
								target[name];
						}
						var name = attributeParts[i];
						if(target.set){
							target.set(name, value);
						}else{
							target[name] = value;
						}
					});
				};
				reversal.rule = rule;
//				(reversalOfAttributes[name] || (reversalOfAttributes[name] = [])).push(reversal);
			}
		}else{
			// it's a full expression, so we create a time-varying bound function with the expression
			var reactiveFunction = Function.apply(this, parameters.concat(['return (' + expression + ')']));
		}
		variables.func = reactiveFunction;
		rule["var-expr-" + name] = variables;
		function getComputation(){
			var waiting = variables.length + 1;
			var values = [], callbacks = [];
			var result, isResolved, stopped;
			var done = function(i){
				return function(value){
					if(stopped){
						return;
					}
					values[i] = value;
					waiting--;
					if(waiting <= 0){
						isResolved = true;
						result = reactiveFunction ? reactiveFunction.apply(this, values) : values[0];
						for(var j = 0; j < callbacks.length;j++){
							callbacks[j](result);
						}
					}
				};
			};
			if(reactiveFunction){
				for(var i = 0; i < variables.length; i++){
					var variable = variables[i];
					get(variable[0], variable.slice(1), done(i));
				}
			}else{
				var variable = variables[0];
				var value = {
					then: function(callback){
						callbacks ? 
							callbacks.push(callback) :
							callback(value); // immediately available
					}
				}
				utils.when(variable[0], function(resolved){
					value = resolved;
					for(var j = 1; j < variable.length; j++){
						if(value && value.get){
							value = value.get(variable[j]);
						}else{
							value = {
								receive: function(callback){
									get(resolved, variable.slice(1), callback);
								},
								put: function(value){
									set(resolved, variable.slice(1), value);
								}
							};
							break;
						}
					}
					for(var j = 0; j < callbacks.length; j++){
						callbacks[j](value);
					}
					// accept no more callbacks, since we have resolved
					callbacks = null;
				});
				return value;
				if(first && first.then){
					return {
						then: function(callback){
							get(variable[0], variable.slice(1), callback);
						}
					};
				}else{
					return variable;
				}
			}
			done(-1)();
			if(result && result.then){
				return result;
			}
			return {
				receive: function(callback){
					if(callbacks){
						callbacks.push(callback);
					}
					if(isResolved){
						callback(result);
					}
				},
				stop: function(){
					// TODO: this is not the right way to do this, we need to remove
					// all the variable listeners and properly destroy this
					stopped = true;
				}
			}
		}
		return rule["var-expr-" + name] = isElementDependent ? {
			forElement: function(element){
				// TODO: at some point may make this async
				var callbacks = [];
				var mostSpecificElement;
				var elementVariables = [];
				// now find the element that matches that rule, in case we are dealing with a child
				var parentElement;
				for(var i = 0; i < variables.length; i++){
					var variable = variables[i];
					var target = variable[0];
					// now find the element that is keyed on
					if(target.forElement){
						target = variable[0] = target.forElement(element);
					}
					// we need to find the most parent element that we need to vary on for this computation 
					var varyOnElement = parentElement = target.element;
					if(mostSpecificElement){
						// check to see if one its parent is the mostSpecificElement
						while(parentElement && parentElement != mostSpecificElement){
							parentElement = parentElement.parentNode;
						}
						// if so, we have a new most specific
					}	
					if(parentElement){
						mostSpecificElement = varyOnElement;
					}
				}
				// make sure we indicate the store we are keying off of
				var computation = mostSpecificElement["expr-result-" + variables.id];
				if(!computation){
					mostSpecificElement["expr-result-" + variables.id] = computation = getComputation();
					computation.element = mostSpecificElement;
				}
				return computation;
			}
		} : getComputation();
	}
	
});