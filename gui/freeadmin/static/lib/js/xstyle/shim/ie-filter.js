/*
    Transforms for IE filters

*/
define([],function(){

	return {
		put: function(value, rule, name){
			value = value.toString();
			if(name == "box-shadow"){
				var parts = value.split(/\s+/);
				var offX = parseFloat(parts[0]);
				var offY = parseFloat(parts[1]);
				var strength = Math.sqrt(offX*offX + offY*offY);
				var direction = (offY > 0 ? 180 : 360) - Math.atan(offX/offY) * 180 / Math.PI;
				rule.setStyle('filter', "progid:DXImageTransform.Microsoft.Shadow(strength=" + strength + ",direction=" + direction + ",color='" + parts[3] + "')");
			}
			if(name == "transform" && value.match(/rotate/)){
				var angle = value.match(/rotate\(([-\.0-9]+)deg\)/)[1] / 180 * Math.PI;
				var cos = Math.cos(angle);
				var sin = Math.sin(angle);
				rule.setStyle('filter',"progid:DXImageTransform.Microsoft.Matrix(" + 
                     "M11=" + cos +", M12=" + (-sin) + ",M21=" + sin + ", M22=" + cos + ", sizingMethod='auto expand')");
			}
			if(name == "opacity"){
				rule.setStyle('filter','alpha(opacity=' + (value * 100) + ')');
				rule.setStyle('zoom', '1');
			}
		}
	};
});

