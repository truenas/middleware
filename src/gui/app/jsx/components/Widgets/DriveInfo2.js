/** @jsx React.DOM */

"use strict";

var React = require("react");
var D3 = require("d3");

var DriveInfo2 = React.createClass({
  getInitialState: function() {
    return {
      context:		""
      ,width:  		""
      ,height:		""
      ,temp:		  ""
      ,tempUnits:	"°C"
      ,sn:			  ""
      ,hdd:       null
      ,ledOff:    null
      ,ledGreen:  null
      ,ledRed:    null
      ,tickCount: 0
    };
  },

  componentDidMount: function() {
	  var hddVar = new Image();
    hddVar.src = '/img/hdd.png';

    var ledOffVar = new Image();
    ledOffVar.src = '/img/led-off.png';

    var ledGreenVar = new Image();
    ledGreenVar.src = '/img/led-green.png';

    var ledRedVar = new Image();
    ledRedVar.src = '/img/led-red.png';


  this.setState({
	  context:	  this.getDOMNode().getContext('2d')
    ,width:  	  this.getDOMNode().width
    ,height:	  this.getDOMNode().height
    ,temp:	    46
    ,sn:		    this.props.sn
    ,hdd:       hddVar
    ,ledOff:    ledOffVar
    ,ledGreen:  ledGreenVar
    ,ledRed:    ledRedVar
    });
    this.paint();
    this.interval = setInterval(this.tick, 200);
  },

  tick: function(){
  	if (this.state.tickCount >= 4) {
  		this.setState({
      	tickCount:	0
    	});
      if (this.state.temp >= 99) {
        this.setState({
          temp: 35
        });
      } else {
        this.setState({
          temp: this.state.temp + 1
        });
      }
  	} else {
  		this.setState({
      	tickCount:	this.state.tickCount + 1
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
  var hddImage = this.state.hdd;
  var ledOffImage = this.state.ledOff;
  var ledGreenImage = this.state.ledGreen;
  var ledRedImage = this.state.ledRed;
  var ticks = this.state.tickCount;

  if (ticks === 0) {

  	var greenGradient=context.createLinearGradient(width-50,0,width-10,0);
  	greenGradient.addColorStop(0, 'ForestGreen');
  	greenGradient.addColorStop(1, 'YellowGreen');

  	var redGradient=context.createLinearGradient(0,10,0,50);
  	redGradient.addColorStop(0, 'FireBrick');
  	redGradient.addColorStop(1, 'Tomato');


  	context.clearRect(0, 0, width, height);

    context.drawImage(hddImage, 11, 2);


  	context.beginPath();
  	context.arc(width-30, 30, 20, 0, 2 * Math.PI, false);
  	if (this.state.temp < 60){
  		context.fillStyle = greenGradient;
  	} else {
  		context.fillStyle = redGradient;
  	}
  	context.fill();

    context.beginPath();
    context.arc(width-30, 75, 20, 0, 2 * Math.PI, false);
    context.fillStyle = greenGradient;
    context.fill();

    context.fillStyle = "Black";
    context.font = "15px Open Sans";
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.fillText(temp,width-30,30);
    context.fillText("OK",width-30,75);
    context.font = "13px Open Sans";
    context.fillText("da2 - 6.0 TB",x,height-18);
    context.font = "11px Open Sans";
    context.fillStyle = "DimGray";
  	context.fillText("SN: "+ sn,x,height-4);

  } else {
    if (ticks === 2 || ticks === 4)
    {
      if (this.state.temp < 60){
        context.drawImage(ledGreenImage, 107, 109);
      } else {
        context.drawImage(ledRedImage, 107, 109);
      }

    } else {
      context.drawImage(ledOffImage, 107, 109);
    }
  }



  },

  render: function() {

  	var version = D3.version;
    return (
      <canvas width={150} height={150} />
    );
  }
});


module.exports = DriveInfo2;