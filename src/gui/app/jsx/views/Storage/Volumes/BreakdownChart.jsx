// VOLUME USAGE STACKED GRAPH
// ==========================
// Shows the usage of resources in a pool, including parity information.

"use strict";

import React from "react";
import TWBS from "react-bootstrap";

const BreakdownChart = React.createClass(

  { getDefaultProps: function () {
    return { used   : 0
           , free   : 0
           , parity : 0
           , total  : 0
           };
  }

  , calcPercent: function ( section ) {
    if ( this.props.total > 0 ) {
      return Math.floor( ( this.props[ section ] / this.props.total ) * 100 );
    } else {
      return 0;
    }
  }

  , render: function () {
    let stackedBar = null;

    if ( this.props.total > 0 ) {
      stackedBar = (
        <TWBS.ProgressBar>
          <TWBS.ProgressBar
            bsStyle = "warning"
            now     = { this.calcPercent( "parity" ) }
            key     = { 3 }
          />
          <TWBS.ProgressBar
            bsStyle = "primary"
            now     = { this.calcPercent( "used" ) }
            key     = { 1 }
          />
        </TWBS.ProgressBar>
      );
    } else {
      stackedBar = <TWBS.ProgressBar bsStyle="primary" active />;
    }

    return stackedBar;
  }

  }
);

export default BreakdownChart;
