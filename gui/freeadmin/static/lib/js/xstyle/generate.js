define([], function(){
	function Generate(domNode){
		return {
			layout: function(layout, rule){
				return function(domNode){
					for(var i = 0; i < layout.length; i++){
						var rule = layout[i];
						var selector = rule.selector;
						var target = document.createElement("div");
						// create the appropriate additions to the elements based on the selectors
						selector.replace(/\.([\w-]+)/, function(t, className){
							target.className = className;
						});
						selector.replace(/#([\w-]+)/, function(t, id){
							target.id = id;
						});
						rule.apply(target);
						domNode.appendChild(target);
					}
				}
			},
			content: function(content, rule){
				return function(domNode){
					domNode.innerHTML = eval(content);
				}
			},
			role: "layout"
		};
	}
	var def = new Generate({});
	Generate.layout = def.layout;
	Generate.content = def.content;
	Generate.role = def.role;
	return Generate; 
})