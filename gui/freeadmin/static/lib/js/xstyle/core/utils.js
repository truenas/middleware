define("xstyle/core/utils", [], function(){
	// some utility functions
	var supportedTags = {};
	return {
		when: function(value, callback){
			return value && value.then ? 
				(value.then(callback) || value) : callback(value);
		},
		convertCssNameToJs: function(name){
			// TODO: put this in a util module since it is duplicated in parser.js
			return name.replace(/-(\w)/g, function(t, firstLetter){
				return firstLetter.toUpperCase();
			});
		},
		isTagSupported: function(tag){
			// test to see if a tag is supported by the browser
			if(tag in supportedTags){
				return supportedTags[tag];
			}
			var elementString = (element = document.createElement(tag)).toString();
			return supportedTags[tag] = !(elementString == "[object HTMLUnknownElement]" || elementString == "[object]");
		},
		extend: function(target, base, error){
			var ref = target.getDefinition(base, true);
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
					error("Extending undefined definition " + base);
				}
			}
			
		}
	};
});