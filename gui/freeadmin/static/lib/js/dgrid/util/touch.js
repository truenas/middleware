define([
	'dojo/on',
	'dojo/query'
], function (on, query) {
	// This module exposes useful functions for working with touch devices.

	var util = {
		// Overridable defaults related to extension events defined below.
		tapRadius: 10,
		dbltapTime: 250,

		selector: function (selector, eventType, children) {
			// summary:
			//		Reimplementation of on.selector, taking an iOS quirk into account
			return function (target, listener) {
				var bubble = eventType.bubble;
				if (bubble) {
					// the event type doesn't naturally bubble, but has a bubbling form, use that
					eventType = bubble;
				}
				else if (children !== false) {
					// for normal bubbling events we default to allowing children of the selector
					children = true;
				}
				return on(target, eventType, function (event) {
					var eventTarget = event.target;

					// iOS tends to report the text node an event was fired on, rather than
					// the top-level element; this may end up causing errors in selector engines
					if (eventTarget.nodeType === 3) {
						eventTarget = eventTarget.parentNode;
					}

					// there is a selector, so make sure it matches
					while (!query.matches(eventTarget, selector, target)) {
						if (eventTarget === target || !children || !(eventTarget = eventTarget.parentNode)) {
							return;
						}
					}
					return listener.call(eventTarget, event);
				});
			};
		},

		countCurrentTouches: function (evt, node) {
			// summary:
			//		Given a touch event and a DOM node, counts how many current touches
			//		presently lie within that node.  Useful in cases where an accurate
			//		count is needed but tracking changedTouches won't suffice because
			//		other handlers stop events from bubbling high enough.

			if (!('touches' in evt)) {
				// Not a touch event (perhaps called from a mouse event on a
				// platform supporting touch events)
				return -1;
			}

			var i, numTouches, touch;
			for (i = 0, numTouches = 0; (touch = evt.touches[i]); ++i) {
				if (node.contains(touch.target)) {
					++numTouches;
				}
			}
			return numTouches;
		}
	};

	function handleTapStart(target, listener, evt, prevent) {
		// Common function for handling tap detection.
		// The passed listener will only be fired when and if a touchend is fired
		// which confirms the overall gesture resembled a tap.

		if (evt.targetTouches.length > 1) {
			return; // ignore multitouch
		}

		var start = evt.changedTouches[0],
			startX = start.screenX,
			startY = start.screenY;

		prevent && evt.preventDefault();

		var endListener = on(target, 'touchend', function (evt) {
			var end = evt.changedTouches[0];
			if (!evt.targetTouches.length) {
				// only call listener if this really seems like a tap
				if (Math.abs(end.screenX - startX) < util.tapRadius &&
						Math.abs(end.screenY - startY) < util.tapRadius) {
					prevent && evt.preventDefault();
					listener.call(this, evt);
				}
				endListener.remove();
			}
		});
	}

	function tap(target, listener) {
		// Function usable by dojo/on as a synthetic tap event.
		return on(target, 'touchstart', function (evt) {
			handleTapStart(target, listener, evt);
		});
	}

	function dbltap(target, listener) {
		// Function usable by dojo/on as a synthetic double-tap event.
		var first, timeout;

		return on(target, 'touchstart', function (evt) {
			if (!first) {
				// first potential tap: detect as usual, but with specific logic
				handleTapStart(target, function (evt) {
					first = evt.changedTouches[0];
					timeout = setTimeout(function () {
						first = timeout = null;
					}, util.dbltapTime);
				}, evt);
			}
			else {
				handleTapStart(target, function (evt) {
					// bail out if first was cleared between 2nd touchstart and touchend
					if (!first) {
						return;
					}
					var second = evt.changedTouches[0];
					// only call listener if both taps occurred near the same place
					if (Math.abs(second.screenX - first.screenX) < util.tapRadius &&
							Math.abs(second.screenY - first.screenY) < util.tapRadius) {
						timeout && clearTimeout(timeout);
						first = timeout = null;
						listener.call(this, evt);
					}
				}, evt, true);
			}
		});
	}

	util.tap = tap;
	util.dbltap = dbltap;

	return util;
});