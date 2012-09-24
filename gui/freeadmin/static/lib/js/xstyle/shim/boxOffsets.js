/*
    cssx/shim/boxOffsets
    (c) copyright 2010, unscriptable.com
    author: john

    LICENSE: see the LICENSE.txt file. If file is missing, this file is subject to the AFL 3.0
    license at the following url: http://www.opensource.org/licenses/afl-3.0.php.

    This cssx plugin fixes lack of box offset positioning in IE6.

    TODO: the logic in here could be improved a bit

*/
define({
	onProperty: function(prop, value){
		if(prop == "bottom"){
			if (value !== 'auto') {
				// optimize common case in which bottom is in pixels already or is 0 (IE always uses '0px' for '0')
				if (value.match(/px$/)) {
					return 'height: expression(cssx_boxOffsets_checkBoxHeight(this, ' + parseInt(value) + '));';
				}
				else {
					return 'height: expression(cssx_boxOffsets_checkBoxHeight(this)); bottom: expression("' + value + '");';
				}
			}
		}
		else {
			if(value !== 'auto') {
				if (value.match(/px$/)) {
					return 'width: expression(cssx_boxOffsets_checkBoxWidth(this, ' + parseInt(value) + '));';
				}
				else {
					return 'width: expression(cssx_boxOffsets_checkBoxWidth(this)); right: expression("' + value + '");';
				}
			}
		}
	}
});

// it's easiest if these functions are global

function cssx_boxOffsets_checkBoxHeight (node, bVal) {
	setTimeout(function(){
		var parent = node.parentNode;
		var preResize = parent.onresize;
		parent.onresize = function(){
			adjust();
			if(preResize){
				preResize.call(this);
			}
		}
	},10);
	adjust();
	function adjust(){
	console.log("checkHieght");
		if(bVal == null){
			bVal = node.style.pixelBottom;
		}
		node.runtimeStyle.bottom = "0px";
	    var style = node.currentStyle,
	        parent = node.offsetParent,
			doc = node.ownerDocument;
	    // are we using box offset positioning? (Note: assumes position:fixed is fixed for IE6)
	    if (parent && style.top != 'auto' && style.position == 'absolute' || style.position == 'fixed') {
	        var height = parent == doc.body ? doc.body.clientHeight : parent.offsetHeight
	                - (node.offsetHeight - node.clientHeight) /* border height */
	                - parseInt(style.paddingTop)- parseInt(style.paddingBottom) /* padding height if px */;
	        height = height - node.offsetTop - bVal + 'px';
	    }
	    else
	        height = '';
	    node.runtimeStyle.height = height;
	}
}

function cssx_boxOffsets_checkBoxWidth (node, rVal) {
	setTimeout(function(){
		var parent = node.parentNode;
		var preResize = parent.onresize;
		parent.onresize = function(){
			adjust();
			if(preResize){
				preResize.call(this);
			}
		}
	},10);
	adjust();
	function adjust(){
		console.log("checkWidth");
		if(rVal == null){
			rVal = node.style.pixelRight;
		}
		node.runtimeStyle.right = "0px";
	    var style = node.currentStyle,
	        parent = node.offsetParent,
			doc = node.ownerDocument;
	    // are we using box offset positioning? (Note: assumes position:fixed is fixed for IE6)
	    if (parent && style.left != 'auto' && style.position == 'absolute' || style.position == 'fixed') {
	        var width = (parent == doc.body ? doc.body.clientWidth : parent.offsetWidth)
	                - (node.offsetWidth - node.clientWidth) /* border width */
	                - parseInt(style.paddingLeft)- parseInt(style.paddingRight) /* padding width if px */;
	        width = width - node.offsetLeft - rVal + 'px';
	    }
	    else
	        width = '';
	    node.runtimeStyle.width = width;
	}
}
