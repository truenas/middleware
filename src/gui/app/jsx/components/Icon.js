/** @jsx React.DOM */

"use strict";

var _     = require("lodash");
var React = require("react");

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
                        , this.props.icoSize
                        , ( "badge-" + this.props.bsBadgeStyle )
                        , this.props.icoClass ], null ).join(" ") }>
        { iconBadge }
      </i>
    );
  }
});

module.exports = Icon;
