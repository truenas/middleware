// VDEV
// ====
// A simple wrapper component for representing a single VDEV.

"use strict";

import React from "react";
import TWBS from "react-bootstrap";

import Icon from "../../../components/Icon";

const VDEV = React.createClass(
  { propTypes:
    { handleDiskAdd  : React.PropTypes.func.isRequired
    , availableDisks : React.PropTypes.array
    , cols           : React.PropTypes.number
    , members        : React.PropTypes.array
    , type           : React.PropTypes.string
    }

  , getDefaultProps: function () {
    return { type    : "VDEV"
           , cols    : 4
           , members : []
           };
  }

  , render: function () {
    let contents = null;

    if ( this.props.members.length ) {
      // TODO
      contents = <h1>TODO</h1>;
    } else {
      // TODO: This layout is a crime against nature
      contents = (
        <span className="text-center">
          <h3><Icon glyph="plus" /></h3>
          <h3>{ "Add " + this.props.type }</h3>
        </span>
      );
    }

    return (
      <TWBS.Col xs={ this.props.cols }>
        { contents }
      </TWBS.Col>
    );
  }

  }
);

export default VDEV;
