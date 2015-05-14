

"use strict";

import _ from "lodash";
import React from "react";

var Icon = React.createClass({
  propTypes: {
      glyph         : React.PropTypes.string.isRequired
    , icoSize       : React.PropTypes.string
    , icoClass      : React.PropTypes.string
    , className     : React.PropTypes.string
    , badgeStyle    : React.PropTypes.string
    , badgeContent  : React.PropTypes.oneOfType([
          React.PropTypes.string
        , React.PropTypes.number
        , React.PropTypes.bool
      ])
  }

  , getDefaultProps: function () {
    return {
        icoSize      : null
      , icoClass     : null
      , bsBadgeStyle : "info"
    };
  }

  , render: function () {
    var iconBadge = null;

    if ( this.props.badgeContent ){
      iconBadge = <span className="badge">{ this.props.badgeContent }</span>;
    }

    return (
      <i onClick   = { this.props.onClick }
         className = { _.without([
                          "fa"
                        , ( "fa-" + this.props.glyph )
                        , this.props.className
                        , ( "badge-" + this.props.bsBadgeStyle )
                        , this.props.icoClass ], null ).join(" ") }
         style     = { { fontSize : this.props.icoSize } }>
        { iconBadge }
      </i>
    );
  }
});

module.exports = Icon;
