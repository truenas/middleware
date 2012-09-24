define([
	"dojo/aspect",
	"dojo/dom-geometry",
	"dojo/dnd/autoscroll",
	"../List"
], function(aspect, domGeometry, autoscroll, List){
	// summary:
	//		This module patches the autoScrollNodes function from the
	//		dojo/dnd/autoscroll module, in order to behave properly for
	//		dgrid TouchScroll components.
	
	var original = autoscroll.autoScrollNodes,
		instances, findEnclosing;
	
	// In order to properly detect autoscroll cases for dgrid+TouchScroll
	// instances, we need to register instances so that we can look them up based
	// on child nodes later.
	
	instances = {};
	aspect.after(List.prototype, "postCreate", function(r){
		var id = this.id;
		// Since this code is only hooked in some cases, don't throw an error here,
		// but do warn since duplicate IDs or improper destruction are likely going
		// to lead to unintended consequences.
		if(instances[id]){
			console.warn("dgrid instance registered with duplicate id '" + id + "'");
		}
		instances[id] = this;
		return r;
	});
	aspect.after(List.prototype, "destroy", function(r){
		delete instances[this.id];
		return r;
	});
	findEnclosing = function(node){
		var id, instance;
		while(node){
			if((id = node.id) && (instance = instances[id])){ return instance; }
			node = node.parentNode;
		}
	};
	
	autoscroll.autoScrollNodes = function(evt){
		var node = evt.target,
			list = findEnclosing(node),
			pos, nodeX, nodeY, thresholdX, thresholdY, dx, dy, oldScroll, newScroll;
		
		if(list){
			// We're inside a dgrid component with TouchScroll; handle using the
			// getScrollPosition and scrollTo APIs instead of scrollTop/Left.
			// All logic here is designed to be functionally equivalent to the
			// existing logic in the original dojo/dnd/autoscroll function.
			
			node = list.touchNode.parentNode;
			pos = domGeometry.position(node, true);
			nodeX = evt.pageX - pos.x;
			nodeY = evt.pageY - pos.y;
			// Use standard threshold, unless element is too small to warrant it.
			thresholdX = Math.min(autoscroll.H_TRIGGER_AUTOSCROLL, pos.w / 2);
			thresholdY = Math.min(autoscroll.V_TRIGGER_AUTOSCROLL, pos.h / 2);
			
			// Check whether event occurred beyond threshold in any given direction.
			// If so, we will scroll by an amount equal to the calculated threshold.
			if(nodeX < thresholdX){
				dx = -thresholdX;
			}else if(nodeX > pos.w - thresholdX){
				dx = thresholdX;
			}
			
			if(nodeY < thresholdY){
				dy = -thresholdY;
			}else if(nodeY > pos.h - thresholdY){
				dy = thresholdY;
			}
			
			// Perform any warranted scrolling.
			if(dx || dy){
				oldScroll = list.getScrollPosition();
				newScroll = {};
				if(dx){ newScroll.x = oldScroll.x + dx; }
				if(dy){ newScroll.y = oldScroll.y + dy; }
				
				list.scrollTo(newScroll);
				return;
			}
		}
		// If we're not inside a dgrid component with TouchScroll, fall back to
		// the original logic to handle scroll on other elements and the document.
		original.call(this, evt);
	};
	
	return autoscroll;
});