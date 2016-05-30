define('xstyle/core/utils', [], function(){
	// some utility functions
	var isXhtml = (document.createElement('div').tagName == 'div');
	var supportedTags = {};
	function someHasProperty(array, property){
		for(var i = 0, l = array.length; i < l; i++){
			var item = array[i];
			if(item && typeof item == 'object' && property in item){
				return true;
			}
		}
	}
	function upperLetter(t, letter){
		return letter.toUpperCase();
	}
	return {
		when: function(value, callback, errorHandler){
			return value && value.then ?
				(value.then(callback, errorHandler) || value) : callback(value);
		},
		whenAll: function(inputs, callback){
			if(someHasProperty(inputs, 'then')){
				// we have asynch inputs, do lazy loading
				return {
					then: function(onResolve, onError){
						var remaining = 1;
						var readyInputs = [];
						for(var i = 0; i < inputs.length; i++){
							var input = inputs[i];
							remaining++;
							if(input && input.then){
								(function(i){
									input.then(function(value){
										readyInputs[i] = value;
										onEach();
									}, onError);
								})(i);
							}else{
								readyInputs[i] = input;
								onEach();
							}
						}
						onEach();
						function onEach(){
							remaining--;
							if(!remaining){
								onResolve(callback(readyInputs));
							}
						}
					},
					inputs: inputs
				};
			}
			// just sync inputs
			return callback(inputs);

		},
		convertCssNameToJs: function(name){
			return name.replace(/-(\w)/g, upperLetter);
		},
		isTagSupported: function(tag){
			// test to see if a tag is supported by the browser
			if(tag in supportedTags){
				return supportedTags[tag];
			}
			var element = document.createElement(tag);
			var supported;
			if(isXhtml){
				// should we really even support this?
				var elementString = element.toString();
				supported = !(elementString == '[object HTMLUnknownElement]' ||
					elementString == '[object]');
			}else{
				supported = (element.tagName == tag.toUpperCase());
			}
			return (supportedTags[tag] = supported);
		},
		extend: function(target, base){
			// takes the target and applies to the base, resolving the base
			// TODO: we may want to support full evaluation of the base,
			// at least if it is in paranthesis (to continue to support
			// unambiguous handling of class names), and attribute definitions
			// like range = input[type=range] {};
			var parts = base.split('.');
			base = parts[0];
			var ref = target.getDefinition(base, 'rules');
			// any subsequent parts after the dot are treated as class names
			parts[0] = '';
			target.selector += (target.extraSelector = parts.join('.'));
			if(ref){
				return this.when(ref, function(ref){
					if(ref.extend){
						ref.extend(target, true);
					}else{
						for(var i in ref){
							target[i] = ref[i];
						}
					}
				});
			}else{
				// extending a native element
				target.tagName = base;
				if(!this.isTagSupported(base)){
					throw new Error('Extending undefined definition ' + base);
				}
			}
			
		},
		someHasProperty: someHasProperty
	};
});