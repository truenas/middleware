/*
    cssx/shim/scrollbar
    (c) copyright 2010, unscriptable.com
    author: john

    LICENSE: see the LICENSE.txt file. If file is missing, this file is subject to the AFL 3.0
    license at the following url: http://www.opensource.org/licenses/afl-3.0.php.
*/
define(
	function () {

		var scrollbarPropRx = /-cssx-scrollbar-(width|height)/;

		// TODO: combine these two functions into one

		function getScrollbarSize () {
			//  summary: figures out the height and width of the scrollbars on this system.
			//  something like this exists in dojox, but we don't want to rely on dojox
			//  Returns an object with w and h properties (width and height, Number) in pixels
			var sbSize = {w: 15, h: 15}; // default
			var testEl = document.createElement('div');
			testEl.style.cssText = 'width:100px;height:100px;overflow:scroll;bottom:100%;right:100%;position:absolute;visibility:hidden;';
			document.body.appendChild(testEl);
			try {
				sbSize = {
					w: testEl.offsetWidth - Math.max(testEl.clientWidth, testEl.scrollWidth),
					h: testEl.offsetHeight - Math.max(testEl.clientHeight, testEl.scrollHeight)
				};
				document.body.removeChild(testEl);
			}
			catch (ex) {
				// squelch
			}
			return sbSize;
		}

		function getSbSize () {
			var sbSize = getScrollbarSize();
			sbSize = { w: sbSize.w + 'px', h: sbSize.h + 'px' };
			getSbSize = function () { return sbSize; };
			return sbSize;
		}

		return {

			onValue: function (value, rule, name) {
				return value.replace(scrollbarPropRx, function (full, which) {
					return which == 'width' ? getSbSize().w : getSbSize().h;
				});
			}

		};

	}
);
