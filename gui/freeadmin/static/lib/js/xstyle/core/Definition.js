define(['xstyle/core/utils', 'xstyle/core/es6'],
		function(utils, es6){
	function Definition(computeValue){
		// computeValue: This is function (or promise to a function) that is called to calculate
		// the value of this definition
		this.computeValue = computeValue;
		if(computeValue && computeValue.reverse){
			this.setReverseCompute(computeValue.reverse);
		}
	}
	var noCacheEntry = {};

	var nextId = 1;
	function contextualizeElement(definition, object, key){
		if(object && object.forElement){
			return {
				forElement: function(element){
					element = object.selectElement ? object.selectElement(element) : element;
					// TODO: use weakmap
					var cacheProperty = ['_cache_' + definition.id];
					if(cacheProperty in element){
						var cacheObserver = element[cacheProperty + 'observe'];
						if(cacheObserver.addKey){
							cacheObserver.addKey(key);
						}
						return element[cacheProperty][key];
					}
					var result = element[cacheProperty] = object.forElement(element);
					var observer = element[cacheProperty + 'observe'] = setupObserve(definition, result, key, {
						elements: [element]
					});
					element.xcleanup = function(destroy){
						if(destroy){
							es6.unobserve(result, observer);
						}
					};
					return result[key];
				}
			};
		}
		// else
	}
	function setupObserve(definition, object, key, invalidated){
		var properties = definition._properties;
		var observer;
		if(typeof object == 'object'){
			// if we haven't recorded any observer for this context, let's
			// setup one now
			observer = function(events){
				for(var i = 0; i < events.length; i++){
					var property = properties[events[i].name];
					if(property && property.invalidate){
						property.invalidate(invalidated);
					}
				}
			};
			es6.observe(object, observer);
			if(observer.addKey){
				observer.addKey(key);
			}
		}
		return observer;
	}
	Definition.prototype = {
		// TODO: make ids have a little better names
		id: 'x-variable-' + nextId++,
		cache: noCacheEntry,
		valueOf: function(){
			// first check to see if we have the variable already computed
			var useCache = this.dependents || this._properties;
			if(useCache){
				// TODO: use when
				if(this.cache !== noCacheEntry){
					return this.cache;
				}
			}
			var definition = this;
			var computeValue = this.computeValue;
			if(computeValue.then){
				return (this.cache = computeValue.then(function(computeValue){
					definition.computeValue = computeValue;
					var value = definition.cache = computeValue();
					if(value && value.then){
						value.then(function(value){
							definition.cache = value;
						});
					}
					return value;
				}));
			}else{
				var value = definition.cache = computeValue();
				if(value && value.then){
					value.then(function(value){
						definition.cache = value;
					});
				}
				return value;
			}
		},
		property: function(key){
			var properties = this._properties || (this._properties = {});
			var propertyDefinition = properties[key];
			if(!propertyDefinition){
				// create the property definition
				var parentDefinition = this;
				propertyDefinition = properties[key] = new Definition(function(){
					return utils.when(parentDefinition.valueOf(), function(object){
						if(object && object.forRule){
							return {
								forRule: function(rule){
									rule = object.selectRule ? object.selectRule(rule) : rule;
									// TODO: use weakmap
									var cacheProperty = ['_cache_' + parentDefinition.id];
									var result;
									if(cacheProperty in rule){
										result = rule[cacheProperty];
									}else{
										result = rule[cacheProperty] = object.forRule(rule);
									}
									if(result && result.forElement){
										return contextualizeElement(parentDefinition, result, key);
									}else{
										var cacheObserve = rule[cacheProperty + 'observe'];
										if(cacheObserve){
											if(cacheObserve.addKey){
												cacheObserve.addKey(key);
											}else{
												rule[cacheProperty + 'observe'] = setupObserve(parentDefinition, result, key, {
													rules: [rule]
												});
											}
										}
									}
									return result[key];
								}
							};
						}
						// else
						if(object && object.forElement){
							return contextualizeElement(parentDefinition, object, key);
						}
						// else
						var cacheObserve = parentDefinition.cacheObserve;
						if(!cacheObserve){
							cacheObserve = parentDefinition.cacheObserve = setupObserve(parentDefinition, object, key);
						}else if(cacheObserve.addKey){
							// used by the es6 to setup setters
							cacheObserve.addKey(key);
						}
						return object[key];
					});
				});
				propertyDefinition.key = key;
				propertyDefinition.parent = this;
				propertyDefinition.put = function(value){
					return utils.when(parentDefinition.valueOf(), function(object){
						if(object.forRule){
							return {
								forRule: function(rule){
									return setForElement(object.forRule(rule));
								}
							};
						}
						function setForElement(object){
							if(object.forElement){
								return {
									forElement: function(element){
										object.forElement(element)[key] = value;
									}
								};
							}
							object[key] = value;
						}
						setForElement(object);
					});
				};
				propertyDefinition.id = this.id + '-' + key;
			}
			return propertyDefinition;
		},
		invalidate: function(args){
			// TODO: there might actually be a collection of observers
			var observer = this.cacheObserve;
			if(observer){
				es6.unobserve(this.cache, observer);
				this.cacheObserve = null;
			}
			this.cache = noCacheEntry;
			var i, l, properties = this._properties;
			for( i in properties){
				properties[i].invalidate(args);
			}
			var dependents = this.dependents || 0;
			for(i = 0, l = dependents.length; i < l; i++){
				try{
					dependents[i].invalidate(args);
				}catch(e){
					console.error(e, 'invalidating a definition');
				}
			}
		},
		dependencyOf: function(dependent){
			(this.dependents || (this.dependents = [])).push(dependent);
		},
		notDependencyOf: function(dependent){
			var dependents = this.dependents || 0;
			for(var i = 0; i < dependents.length; i++){
				if(dependents[i] === dependent){
					dependents.splice(i--, 1);
				}
			}
		},
		setReverseCompute: function(reverse){
			this.put = function(){
				var result = reverse.apply(this, arguments);
				this.invalidate();
				return result;
			};
		},
		setCompute: function(compute){
			this.computeValue = compute;
			if(compute && compute.reverse){
				this.setReverseCompute(compute.reverse);
			}
			this.invalidate();
		},
		setSource: function(value){
			this.computeValue = function(){
				return value;
			};
			this.invalidate();
		},
		observe: function(listener){
			// shorthand for setting up a real invalidation scheme
			if(this.computeValue){
				listener(this.valueOf());
			}
			var definition = this;
			return this.dependencyOf({
				invalidate: function(){
					listener(definition.valueOf());
				}
			});
		},
		newElement: function(){
			return utils.when(this.valueOf(), function(value){
				return value && value.newElement && value.newElement();
			});
		}
	};
	return Definition;
});