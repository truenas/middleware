define(["dojo/_base/declare", "dojo/dom-geometry", "dijit/registry"],
function(declare, domGeometry, registry){
	return declare(null, {
		// summary:
		//		A dgrid extension which will add the grid to the dijit registry,
		//		so that startup() will be successfully called by dijit layout widgets
		//		with dgrid children.
		
		// Defaults normally imposed on _WidgetBase by container widget modules:
		minSize: 0, // BorderContainer
		maxSize: Infinity, // BorderContainer
		layoutPriority: 0, // BorderContainer
		showTitle: true, // StackContainer
		
		buildRendering: function(){
			registry.add(this);
			this.inherited(arguments);
			// Note: for dojo 2.0 may rename widgetId to dojo._scopeName + "_widgetId"
			this.domNode.setAttribute("widgetId", this.id);
		},
		
		startup: function(){
			if(this._started){ return; }
			this.inherited(arguments);
			
			var widget = registry.getEnclosingWidget(this.domNode.parentNode);
			// If we have a parent layout container widget, it will handle resize,
			// so remove the window resize listener added by List.
			if(widget && widget.isLayoutContainer){
				this._resizeHandle.remove();
			}
		},

		destroyRecursive: function() {
			this.destroy();
		},
		
		destroy: function(){
			this.inherited(arguments);
			registry.remove(this.id);
		},
		
		getChildren: function(){
			// provide hollow implementation for logic which assumes its existence
			// (e.g. dijit/form/_FormMixin)
			return [];
		},
		
		isLeftToRight: function(){
			// Implement method expected by Dijit layout widgets
			return !this.isRTL;
		},
		
		resize: function(changeSize){
			// Honor changeSize parameter used by layout widgets, and resize grid
			if(changeSize){
				domGeometry.setMarginBox(this.domNode, changeSize);
			}
			
			this.inherited(arguments);
		},
		
		_set: function(prop, value){
			// summary:
			//		Simple analogue of _WidgetBase#_set for compatibility with some
			//		Dijit layout widgets which assume its existence.
			this[prop] = value;
		},
		
		watch: function(){
			// summary:
			//		dgrid doesn't support watch; this is a no-op for compatibility with
			//		some Dijit layout widgets which assume its existence.
		},
		
		getParent: function(){
			// summary:
			//		Analogue of _WidgetBase#getParent for compatibility with for example
			//		dijit._KeyNavContainer.
			return registry.getEnclosingWidget(this.domNode.parentNode);
		}
	});
});
