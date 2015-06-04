// VIEWER MODAL MIXIN
// ==================
// Mixin for displaying the modal overlay in certain Viewer modes

"use strict"

const ViewerModal =
  { componentDidMount: function () {
      window.addEventListener( "keyup", this.handleEscClose );
    }

  , componentWillUnmount: function () {
      window.removeEventListener( "keyup", this.handleEscClose );
    }

  , handleEscClose: function ( event ) {
      if ( event.which === 27 && this.dynamicPathIsActive() ) {
        event.preventDefault();
        event.stopPropagation();
        this.returnToViewerRoot();
      }
    }

  , handleClickOut: function ( event, componentID ) {
      if ( event.dispatchMarker === componentID ) {
        this.returnToViewerRoot();
      }
    }
  };

export default ViewerModal;
