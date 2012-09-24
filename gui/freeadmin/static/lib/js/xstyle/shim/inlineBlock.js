/*
    cssx/shim/inlineBlock
    (c) copyright 2010, unscriptable.com
    author: john

    LICENSE: see the LICENSE.txt file. If file is missing, this file is subject to the AFL 3.0
    license at the following url: http://www.opensource.org/licenses/afl-3.0.php.

    This cssx plugin fixes lack of inline-block support in IE6 and IE7

*/
define(
	function () {

		return {

			onProperty: function (name, value) {
				// processor: the cssx processor in context
				// parseArgs:
				// 		propName: String
				// 		value: String
				// 		selectors: String|Array
				// 		sheet: String
				if ('inline-block' === value){
					return 'display: inline; zoom: 1';
				}
			}

		};

	}
);
