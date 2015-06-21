

"use strict";

import React from "react";
import _ from "lodash";

import Icon from "./Icon";

var Widget = React.createClass({

  render: function () {
    var widgetStyle  = this.props.position ? { left: this.props.position[0]
                                             , top: this.props.position[1] }
                                           : {};
    var widgetContetnStyle  = this.props.position
                              ? { width: this.props.dimensions[0]
                                  , height: this.props.dimensions[1] - 16 }
                              : {};
    return (
      <div  ref = { this.props.refHolder }
            onMouseDown = { this.props.onMouseDownHolder }
            className={"widget " + this.props.size + ( this.props.inMotion
                                                        ? " in-motion"
                                                        : "" ) }
            style= { widgetStyle }>
        <header>
          <span className="widgetTitle">
            {this.props.title}
            <Icon
              glyph="gear"
              icoSize="lg"
              onTouchStart = { this.props.changeSize }
              onClick      = { this.props.changeSize } />
            </span>
        </header>
        <div className="widget-content"
             style= { widgetContetnStyle }>
          { this.props.children }
        </div>
      </div>

    );
  }
});

module.exports = Widget;

