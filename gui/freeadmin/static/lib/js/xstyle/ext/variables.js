/* variable replacement for CSS*/
define([], function(){
	return function(variables){
		return {
			all: function(value, rule, name){
				value.replace(/$[\w+]/g, function(variable){
					return variables[variable];
				});
			}
		};
	}
});