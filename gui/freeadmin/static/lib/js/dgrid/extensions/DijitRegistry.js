define(["dojo/_base/declare", "dijit/registry"],
function(declare, registry){
	return declare([], {
		// summary:
		//		A dgrid extension which will add the grid to the dijit registry,
		//		so that startup() will be successfully called by dijit layout widgets
		//		with dgrid children.
		
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
		}
	});
});
