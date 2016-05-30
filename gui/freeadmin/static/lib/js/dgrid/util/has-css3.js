define([
	'dojo/has'
], function (has) {
	// This module defines feature tests for CSS3 features such as transitions.
	// The css-transitions, css-transforms, and css-transforms3d has-features
	// can report either boolean or string:
	// * false indicates no support
	// * true indicates prefix-less support
	// * string indicates the vendor prefix under which the feature is supported

	var cssPrefixes = ['ms', 'O', 'Moz', 'Webkit'];

	function testStyle(element, property) {
		var style = element.style,
			i;

		if (property in style) {
			// Standard, no prefix
			return true;
		}
		property = property.slice(0, 1).toUpperCase() + property.slice(1);
		for (i = cssPrefixes.length; i--;) {
			if ((cssPrefixes[i] + property) in style) {
				// Vendor-specific css property prefix
				return cssPrefixes[i];
			}
		}

		// Otherwise, not supported
		return false;
	}

	has.add('css-transitions', function (global, doc, element) {
		return testStyle(element, 'transitionProperty');
	});

	has.add('css-transforms', function (global, doc, element) {
		return testStyle(element, 'transform');
	});

	has.add('css-transforms3d', function (global, doc, element) {
		return testStyle(element, 'perspective');
	});

	has.add('transitionend', function () {
		// Infer transitionend event name based on CSS transitions has-feature.
		var tpfx = has('css-transitions');
		if (!tpfx) {
			return false;
		}
		if (tpfx === true) {
			return 'transitionend';
		}
		return {
			ms: 'MSTransitionEnd',
			O: 'oTransitionEnd',
			Moz: 'transitionend',
			Webkit: 'webkitTransitionEnd'
		}[tpfx];
	});

	return has;
});
