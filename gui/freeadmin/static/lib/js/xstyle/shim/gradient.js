/*
    Handles gradients
*/
define([],function(vendor){
	var colorString = /#(\w{6})/;
	var createGradient = {
		"-webkit-": function(type, position, from, to){
			return "background-image: -webkit-gradient(" + type.substring(0, 6) + ", left top, left bottom, from(" + from + "), to(" + to + "))";
		},
		"-moz-": function(type, position, from, to){
			return "background-image: -moz-" + type + "(" + position + "," + from + "," + to + ")";
		},
		"-o-": function(type, position, from, to){
			return "background-image: -o-" + type + "(" + position + "," + from + "," + to + ")";
		},
		"-ms-": function(type, position, from, to){
			
			from = from.match(colorString);
			to = to.match(colorString);
			if(from && to){ 
				// must disable border radius for IE
				return "border-radius: 0px; filter: progid:DXImageTransform.Microsoft.gradient(startColorstr=#FF" + from[1] + ",endColorstr=#FF" + to[1] +",gradientType=" + (position=="left" ? 1 : 0) + ");";
			}
		}
	}[vendor.prefix];
	return {
		onIdentifier: function(name, value, rule){
			var parts = value.match(/(\w+-gradient)\(([^\)]*)\)/);
			var type = parts[1];
			var args = parts[2].split(/,\s*/);
			var position = args[0];
			var start = args[1];
			var end = args[2];
			return createGradient(type, position, start, end);
		}
	};
});

