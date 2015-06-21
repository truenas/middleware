// Generic Disclosure Triangle based React Components
// ===============================
// General purpose disclosure Triangles, they can be used to show/hide any
// data(paragraphs/lists/Twitter Bootstrap panels (TWBS.panel) ,etc)

"use strict";

import React from "react";

// Icons
import Icon from "../Icon";

var DiscTri = React.createClass(

  { propTypes: { headerShow      : React.PropTypes.string
               , headerHide      : React.PropTypes.string
               , DiscShowImg     : React.PropTypes.node
               , DiscHideImg     : React.PropTypes.node
               , onDisc          : React.PropTypes.func
               , defaultExpanded : React.PropTypes.bool
    }

  , getDefaultProps : function ( ) {
      return { headerShow   : "Hide"
             , headerHide   : "Show"
             , DiscShowImg  : ( <Icon glyph = "toggle-down"
                                    icoSize = "1em" /> )
             , DiscHideImg  : ( <Icon glyph = "toggle-right"
                                    icoSize = "1em" /> )
      };
    }

  , getInitialState: function ( ) {
    var defaultExpanded = this.props.defaultExpanded !== null ?
      this.props.defaultExpanded : this.props.expanded !== null ?
        this.props.expanded : false;

    return {
      expanded: defaultExpanded
    };
  }

  , isExpanded: function ( ) {
      return this.state.expanded;
    }

  , onHandleToggle: function ( e ) {
      e.preventDefault();
      if ( typeof this.props.onDisc === "function" ) {
        this.props.onDisc();
      }
      this.setState( { expanded: !this.state.expanded } );
    }

  , render: function ( ) {
      // TODO: change to classnames?
      var text = this.props.headerHide;
      var img  = this.props.DiscHideImg;
      var cln  = "disc-hide";
      if ( this.isExpanded() ) {
        text   = this.props.headerShow;
        img    = this.props.DiscShowImg;
        cln    = "disc-show";
      }
      return (
        <div className = "disclosure-triangle">
          <div onClick={this.onHandleToggle}
                className="disc-title" >
            {img}{text}
          </div>
          <div className={ cln }>
            {this.props.children}
          </div>
        </div>
      );
    }
  }
);

module.exports = DiscTri;
