define([
	'dojo/_base/declare',
	'dojo/_base/array',
	'dojo/dom-geometry'
], function (declare, arrayUtil, domGeometry) {
	return declare(null, {
		resize: function (changeSize) {
			if (changeSize) {
				domGeometry.setMarginBox(this.domNode, changeSize);
			}
			arrayUtil.forEach(this.getChildren(), function (child) {
				if (child.resize) {
					child.resize();
				}
			});
			this.inherited(arguments);
		}
	});
});
