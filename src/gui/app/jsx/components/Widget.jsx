"use strict";

var React  = require( "react" );

var Icon   = require( "./Icon" );

var Widget = React.createClass({
  getInitialState: function () {
    return {  size    : this.props.size
            , count   : 0
            , sizeArr : [ "s", "m", "l" ]
    };
  }

, changeSize: function () {
    //console.log( "changeSize" );
    var i = ( this.state.count < this.state.sizeArr.length ? this.state.count : 0 );
    //console.log( i );
    i++;
    //console.log( i );

    this.setState( {    size   : this.state.sizeArr[ i - 1 ] + this.state.size.substring( 1, this.state.size.length )                      , count  : i
                   } );
  }

, render: function () {
    return (
      <div className={"widget " + this.state.size}>
        <header>
          <span className="widgetTitle">
            {this.props.title}
            <Icon
              glyph="gear"
              icoSize="lg"
              onTouchStart = { this.changeSize }
              onClick      = { this.changeSize } />
            </span>
        </header>
        <div className="widget-content">
          { this.props.children }
        </div>
      </div>

    );
  }
});

module.exports = Widget;

