

"use strict";

var React   =   require("react");

var Widget  =   require("../Widget");

var DriveInfo2 = React.createClass({
  getInitialState: function () {
    return {
      context:		""
      ,width:  		""
      ,height:		""
      ,temp:		  ""
      ,tempUnits:	"°C"
      ,sn:			  ""
      ,size:      ""
      ,name:      ""
      ,hdd:       null
      ,ledOff:    null
      ,ledGreen:  null
      ,ledRed:    null
      ,tickCount: 0
    };
  },

  componentDidMount: function () {
	  var hddVar = new Image();
    if (this.props.diskData.type === "ssd") {
      hddVar.src = '/img/ssd.png';
    } else {
    hddVar.src = '/img/hdd.png';
    }

    var ledOffVar = new Image();
    ledOffVar.src = '/img/led-off.png';

    var ledGreenVar = new Image();
    ledGreenVar.src = '/img/led-green.png';

    var ledRedVar = new Image();
    ledRedVar.src = '/img/led-red.png';


  this.setState({
	  context:	  this.refs.canvas.getDOMNode().getContext('2d')
    ,width:  	  this.refs.canvas.getDOMNode().width
    ,height:	  this.refs.canvas.getDOMNode().height
    ,temp:	    46
    ,sn:		    this.props.diskData.sn
    ,size:      this.props.diskData.size
    ,name:      this.props.diskData.name
    ,hdd:       hddVar
    ,ledOff:    ledOffVar
    ,ledGreen:  ledGreenVar
    ,ledRed:    ledRedVar
    });
    this.paint();
    this.interval = setInterval(this.tick, 200);
  },

  tick: function (){
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

  paint: function () {
	var width = this.state.width;
	var height = this.state.height;
	var x = parseInt(width/2);
	var y = parseInt(height/2);
	var context = this.state.context;
	var temp = this.state.temp.toString()+this.state.tempUnits;
	var sn = this.state.sn;
  var name = this.state.name;
  var size = this.state.size;
  var hddImage = this.state.hdd;
  var ledOffImage = this.state.ledOff;
  var ledGreenImage = this.state.ledGreen;
  var ledRedImage = this.state.ledRed;
  var ticks = this.state.tickCount;

  if (ticks === 0) {

  	var greenGradient=context.createLinearGradient(115,0,155,0);
  	greenGradient.addColorStop(0, 'ForestGreen');
  	greenGradient.addColorStop(1, 'YellowGreen');

    var yellowGradient=context.createLinearGradient(115,0,155,0);
    yellowGradient.addColorStop(0, '#F09609');
    yellowGradient.addColorStop(1, '#EBC232');

  	var redGradient=context.createLinearGradient(115,0,155,0);
  	redGradient.addColorStop(0, 'FireBrick');
  	redGradient.addColorStop(1, 'Tomato');


  	context.clearRect(0, 0, width, height);

    context.drawImage(hddImage, 19, 6);


  	context.beginPath();
  	context.arc(width-30, 30, 20, 0, 2 * Math.PI, false);
  	if (this.state.temp < 50){
  		context.fillStyle = greenGradient;
  	} else if (this.state.temp >= 50 && this.state.temp < 60) {
  		context.fillStyle = yellowGradient;
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
    context.fillText(name + " - " + size,x,height-28);
    context.font = "11px Open Sans";
    context.fillStyle = "DimGray";
  	context.fillText("SN: "+ sn,x,height-14);

  } else {
    if (ticks === 2 || ticks === 4)
    {
      if (this.state.temp < 60){
        context.drawImage(ledGreenImage, 115, 113);
      } else {
        context.drawImage(ledRedImage, 115, 113);
      }

    } else {
      context.drawImage(ledOffImage, 115, 113);
    }
  }



  },

  render: function () {
    return (
      <Widget
         positionX  =  {this.props.positionX}
         positionY  =  {this.props.positionY}
         title      =  {this.props.title}
         size       =  {this.props.size} >

        <canvas ref="canvas" width={165} height={165} />
      </Widget>
    );
  }
});


module.exports = DriveInfo2;