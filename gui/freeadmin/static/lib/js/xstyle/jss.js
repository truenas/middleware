define([], function(){
	var objectWatch = {}.watch;
	function JSS(data){
		//TODO: record all rules so that additional JSS can be layered on top
		return {
			layout: function(layout, rule){
				return {
					render: function(domNode){
						for(var i = 0; i < layout.length; i++){
							var rule = layout[i];
							var selector = rule.selector.substring(1);
							var value = data.get ? data.get(selector) : data[selector];
							if(data.watch != objectWatch){
								data.watch(selector, function(name, oldValue, value){
									renderValue(value)
								});
							}
							function renderValue(value){
								if(value !== undefined){
									var target = document.createElement("div");
									rule.renderInto(target);
								}
							}
							rule.renderInto(target);
							domNode.appendChild(target);
						}
					},
					cssText: rule.selector.replace(/\//g, "[data-path=$1]")
				}
			}
		};
	}
	return JSS; 
});