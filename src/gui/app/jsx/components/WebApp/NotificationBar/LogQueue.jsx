// LOG / QUEUE DISPLAY COMPONENT
// =============================
// Used in the Notification Bar as a generic way to display serial data queues.

"use strict";

import React from "react";
import TWBS from "react-bootstrap";

import Icon from "../../Icon";

const LogQueue = React.createClass(
  { propTypes:
    { glyph     : React.PropTypes.string.isRequired
    , className : React.PropTypes.string
    , active    : React.PropTypes.array
    , log       : React.PropTypes.array
    }

  , handleToggleClick: function ( event ) {
    if ( this.props.visible === false ) {
      event.stopPropagation();
      this.props.requestVisibility();
    }
  }

  , handleNullClick: function ( event ) {
    event.stopPropagation();
  }

  , createLogItem: function ( rawItem, index ) {
    let statusDisplay;

    switch ( rawItem.status ) {
      case "in-progress":
        statusDisplay = (
          <TWBS.ProgressBar
            bsStyle = "info"
            now     = { rawItem.progress }
            label   = "%(percent)s%"
          />
        );
        break;

      case "pending":
        statusDisplay = (
          <TWBS.ProgressBar
            active
            bsStyle = "info"
            now     = { 100 }
          />
        );
        break;

      case "warning":
      case "info":
      case "done":
        statusDisplay = <span>{ rawItem.details }</span>;
        break;

      default:
        // Do nothing
        statusDisplay = <span></span>;
        break;
    }

    return (
      <div key       = { index }
           className = "item">
        <h4>{ rawItem.description }</h4>
        <div className = "details">{ rawItem.details }</div>
        <div className = "info">{ rawItem.info }</div>
        <div className="status">
          { statusDisplay }
        </div>



      </div>
    );
  }

  , render: function () {
      var activeSection = null;
      var logSection    = null;

      if ( this.props.active.length ) {
        activeSection = <span>
                          <h4>ACTIVE</h4>
                          { this.props.active.map( this.createLogItem ) }
                        </span>;
      }
      if ( this.props.log.length ) {
        logSection = <span>
                       <h4>LOG</h4>
                       { this.props.log.map( this.createLogItem ) }
                     </span>;
      }

      return (
        <div className = "notification-bar-icon"
             onClick   = { this.handleToggleClick } >

          <Icon glyph        = { this.props.glyph }
                icoSize      = "3x"
                badgeContent = { this.props.active.length }/>

          <div className = {[ "notification-box"
                            , this.props.className
                            , this.props.visible ? "visible" : "hidden"
                            ].join( " " )
                           }
               onClick   = { this.handleNullClick }>
          <div className = "notification-box-header">
            {/* jscs: disable */}
            <span>You have <strong>{ this.props.active.length } new </strong> events </span>
            {/* jscs: enable */}
            <a className = "right" href="#">View all</a>
          </div>

            { activeSection }
            { logSection }

          </div>
        </div>
      );
    }

  }
);

export default LogQueue;
