define([], function(){
	return document.defaultView.getComputedStyle ?
		function(node){
			return node.ownerDocument.defaultView.getComputedStyle(node, null);
		} :
		function(node){
			return node.currentStyle || {};
		};
});