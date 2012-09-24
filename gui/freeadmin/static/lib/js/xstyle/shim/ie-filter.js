/*
    Transforms to IE filters

*/
define([],function(){

	/*var filters = {
		return "filter: progid:DXImageTransform.Microsoft.DropShadow(
		
	}*/
	return {
		onProperty: function(name, value){
			var parts = value.split(/\s+/);
			if(name == "box-shadow"){
				var offX = parseFloat(parts[0]);
				var offY = parseFloat(parts[1]);
				var strength = Math.sqrt(offX*offX + offY*offY);
				var direction = (offY > 0 ? 180 : 360) - Math.atan(offX/offY) * 180 / Math.PI;
				return "filter: progid:DXImageTransform.Microsoft.Shadow(strength=" + strength + ",direction=" + direction + ",color='" + parts[3] + "');"
			}
			if(name == "transform" && value.match(/rotate/)){
				var angle = value.match(/rotate\(([-\.0-9]+)deg\)/)[1] / 180 * Math.PI;
				var cos = Math.cos(angle);
				var sin = Math.sin(angle);
				return "filter: progid:DXImageTransform.Microsoft.Matrix(" + 
                     "M11=" + cos +", M12=" + (-sin) + ",M21=" + sin + ", M22=" + cos + ", sizingMethod='auto expand');";
			}
		}
	};
});

