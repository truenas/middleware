// Throbber
// ========

"use strict";

import React from "react";

var Throbber = React.createClass(

  { propTypes: { bsStyle   : React.PropTypes.oneOf( [ "primary"
                                                    , "info"
                                                    , "danger"
                                                    , "warning"
                                                    , "success" ] )
               , size      : React.PropTypes.number
               , className : React.PropTypes.string
    }

  , render: function () {
      var throbberSize  = this.props.size ?
        { height: this.props.size + "px"
        , width: this.props.size + "px" } : null;
      var bsStyle       = this.props.bsStyle ?
        " throbber-" + this.props.bsStyle : "";
      var throbberClass = this.props.className ?
        " " + this.props.className : "";

      return (
        <div className={ "throbber" + bsStyle + throbberClass }>
           <span className="throbber-inner" style = { throbberSize } />
        </div>
      );
    }

  }
);

module.exports = Throbber;
