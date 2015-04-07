"use strict";

module.exports = {

    dynamicPathIsActive: function() {
      if ( this.context.router.getCurrentParams()[ this.props.viewData.routing.param ] ) {
        return true;
      } else {
        return false;
      }
    }

};
