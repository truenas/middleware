// Service Item Template
// =====================


"use strict";

var React      = require("react");
var TWBS       = require("react-bootstrap");

var viewerUtil = require("../../components/Viewer/viewerUtil");
var editorUtil = require("../../components/Viewer/Editor/editorUtil");

var ServiceItem = React.createClass({

    propTypes: {
      item: React.PropTypes.object.isRequired
    }

  , render: function() {

    var pid = null;

    if ( typeof this.props.item["pid"] === "number" ) {
      pid = <h4 className="text-muted">{ viewerUtil.writeString( "PID: " + this.props.item["pid"], "\u200B" ) }</h4>;
    }

    return (
      <div className="viewer-item-info">
        <TWBS.Grid fluid>

        {/* General information */}
        <TWBS.Row>
          <TWBS.Col xs={3}
                    className="text-center">
            <viewerUtil.ItemIcon primaryString   = { this.props.item["name"] }
                                 fallbackString  = { this.props.item["name"] } />
          </TWBS.Col>
          <TWBS.Col xs={9}>
            <h3>{ this.props.item["name"] }</h3>
            <h4 className="text-muted">{ viewerUtil.writeString( this.props.item["state"], "\u200B" ) }</h4>
            { pid }
            <hr />
          </TWBS.Col>
        </TWBS.Row>

        </TWBS.Grid>
      </div>
    );
  }

});

module.exports = ServiceItem;
