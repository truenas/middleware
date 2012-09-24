define([], function(){
	// This module defines miscellaneous utility methods.
	
	var util = {
		defaultDelay: 15,
		throttle: function(cb, context, delay){
			// summary:
			//		Returns a function which calls the given callback at most once per
			//		delay milliseconds.  (Inspired by plugd)
			var ran = false;
			delay = delay || util.defaultDelay;
			return function(){
				if(ran){ return; }
				ran = true;
				cb.apply(context, arguments);
				setTimeout(function(){ ran = false; }, delay);
			}
		},
		throttleDelayed: function(cb, context, delay){
			// summary:
			//		Like throttle, except that the callback runs after the delay,
			//		rather than before it.
			var ran = false;
			delay = delay || util.defaultDelay;
			return function(){
				if(ran){ return; }
				ran = true;
				var a = arguments;
				setTimeout(function(){
					ran = false;
					cb.apply(context, a);
				}, delay);
			}
		},
		debounce: function(cb, context, delay){
			// summary:
			//		Returns a function which calls the given callback only after a
			//		certain time has passed without successive calls.  (Inspired by plugd)
			var timer;
			delay = delay || util.defaultDelay;
			return function(){
				if(timer){
					clearTimeout(timer);
					timer = null;
				}
				var a = arguments;
				timer = setTimeout(function(){
					cb.apply(context, a);
				}, delay);
			}
		}
	};
	return util;
});