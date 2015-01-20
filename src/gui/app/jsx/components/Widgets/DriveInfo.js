/** @jsx React.DOM */

"use strict";

var React   =   require("react");
var D3      =   require("d3");

var Widget  = 	require("../Widget");

var DriveInfo = React.createClass({
  getInitialState: function() {
    return {
      context:		""
      ,width:  		""
      ,height:		""
      ,temp:		""
      ,tempUnits:	"°C"
      ,sn:			""
    };
  },

  componentDidMount: function() {
	this.setState({
	  context:	  this.refs.canvas.getDOMNode().getContext('2d')
      ,width:  	  this.refs.canvas.getDOMNode().width
      ,height:	  this.refs.canvas.getDOMNode().height
      ,temp:	55
      ,sn:		this.props.sn
    });
    this.paint();
    this.interval = setInterval(this.tick, 1000);
  },

  tick: function(){
  	if (this.state.temp >= 99) {
  		this.setState({
      	temp:	35
    	});
  	} else {
  		this.setState({
      	temp:	this.state.temp + 1
    	});
  	}

    this.paint();
  },

  paint: function() {
	var width = this.state.width;
	var height = this.state.height;
	var x = width/2;
	var y = height/2;
	var context = this.state.context;
	var temp = this.state.temp.toString()+this.state.tempUnits;
	var sn = this.state.sn;

	var greenGradient=context.createLinearGradient(0,x,0,0);
	greenGradient.addColorStop(0, 'ForestGreen');
	greenGradient.addColorStop(1, 'YellowGreen');

	var redGradient=context.createLinearGradient(0,x,0,0);
	redGradient.addColorStop(0, 'FireBrick');
	redGradient.addColorStop(1, 'Tomato');


	context.clearRect(0, 0, width, height);

	context.fillStyle = "black";
	context.font="128px FontAwesome";
	context.textAlign = 'center';
	context.textBaseline = 'middle';
	context.fillText(String.fromCharCode("0xff0a0"),x,y-10);

	context.beginPath();
	context.arc(width-30, 30, 20, 0, 2 * Math.PI, false);
	if (this.state.temp < 60){
		context.fillStyle = greenGradient;
	} else {
		context.fillStyle = redGradient;
	}
	context.fill();

  	context.fillStyle = "black";
   	context.font = "15px Open Sans";
   	context.textAlign = 'center';
	context.textBaseline = 'middle';
	context.fillText(temp,width-30,30);
	context.fillText(sn,x,height-15);


    context.rotate(Math.PI / 1.33);
    context.fillStyle = 'ForestGreen';
    context.fillRect(-50, -50, 100, 25);

    context.rotate(Math.PI);
    context.fillStyle = "black";
    context.font = "bold 11px Open Sans";
    context.fillText("SMART: OK",0,38);
    context.rotate(-1*(Math.PI));

	context.rotate(-1*(Math.PI / 1.33));
  },

  render: function() {

  	var version = D3.version;
    return (
      <Widget
    	   positionX  =  {this.props.positionX}
    	   positionY  =  {this.props.positionY}
    	   title      =  {this.props.title}
    	   size       =  {this.props.size} >

        <canvas ref="canvas" width={150} height={150} />
      </Widget>
    );
  }
});


module.exports = DriveInfo;