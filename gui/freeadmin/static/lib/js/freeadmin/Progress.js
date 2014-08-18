define([
  "dojo/_base/declare",
  "dojo/dom-attr",
  "dojo/dom-style",
  "dojo/request/xhr",
  "dijit/_Widget",
  "dijit/_TemplatedMixin",
  "dijit/form/TextBox",
  "dijit/form/Button",
  "dijit/layout/TabContainer",
  "dijit/layout/ContentPane",
  "dijit/ProgressBar",
  "dojox/timing",
  "dojox/string/sprintf",
  "dojo/text!freeadmin/templates/progress.html"
  ], function(
  declare,
  domAttr,
  domStyle,
  xhr,
  _Widget,
  _Templated,
  TextBox,
  Button,
  TabContainer,
  ContentPane,
  ProgressBar,
  timing,
  sprintf,
  template) {

  var Progress = declare("freeadmin.Progress", [ _Widget, _Templated ], {
    templateString : template,
    _numSteps: 1,
    _curStep: 1,
    _mainProgress: "",
    _subProgress: "",
    _iter: 0,
    name : "",
    backupProgress: false,
    fileUpload: false,
    mode: "advanced",
    poolUrl: "",
    steps: "",
    message: "",
    postCreate : function() {

      var me = this;

      this._numSteps = this.steps.length;
      this._iter = 0;
      this._perStep = 100 / this._numSteps;
      this._mainProgress = ProgressBar({
        indeterminate: true,
        style: {width: "280px"}
      }, this.dapMainProgress);

      this._subProgress = ProgressBar({
        indeterminate: true,
        style: {width: "280px"}
      }, this.dapSubProgress);

      if(this.mode == "simple") {
        domStyle.set(this.dapMain, "display", "none");
        domStyle.set(this.dapSubLabel, "display", "none");
        domStyle.set(this.dapDetails, "display", "none");
        domStyle.set(this.dapETA, "display", "none");
      }

      if(this.backupProgress) {
        this.update("");
      }

      this.inherited(arguments);

    },
    _masterProgress: function(curSub) {
      var initial = this._perStep * (this._curStep - 1);
      this._mainProgress.update({
        maximum: 100,
        progress: initial + ((this._perStep / 100) * curSub),
        indeterminate: false
      });
    },
    update: function(uuid) {
      var me = this;
      if(uuid) this.uuid = uuid;
      if(!this.dapMainLabel) return;
      if(!this.backupProgress) this.message = this.steps[this._curStep-1];
      this.dapMainLabel.innerHTML = sprintf("(%d/%d) %s", this._curStep, this._numSteps, this.message.label);
      if(this.fileUpload && this._curStep == 1) {
        xhr.get('/progress', {
          headers: {"X-Progress-ID": me.uuid}
        }).then(function(data) {
          var obj = eval(data);
          if(obj.state == 'uploading') {
            var perc = Math.ceil((obj.received / obj.size)*100);
            if(perc == 100) {
              me._subProgress.update({'indeterminate': true});
              me._masterProgress(perc);
              if(me._numSteps == 1) {
                return;
              }
              me._curStep += 1;
              setTimeout(function() {
                me.update();
              }, 1000);
            } else {
              me._subProgress.update({
                maximum: 100,
                progress: perc,
                indeterminate: false
              });
              me._masterProgress(perc);
            }
          }
          if(obj.state == 'starting' || obj.state == 'uploading') {
            if(obj.state == 'starting' && me._iter >= 3) {
              return;
            }
            setTimeout(function() {
              me.update();
            }, 1000);
          }
        });
        me._iter += 1;

      } else if (this.backupProgress) {
        xhr.get(me.poolUrl, {
          handleAs: "json"
        }).then(function(data) {
          if(data.step) {
            me._curStep = data.step;
          }
          if(data.numSteps) {
            me._numSteps = data._numSteps;
          }
          if(data.message) {
            me._message = data.message;
          }
          if(data.status == 'error' || data.status == 'finished') {
            me.onFinished()
          }
          if(data.percent) {
            if(data.percent == 100) {
              me._subProgress.update({'indeterminate': true});
              me._masterProgress(data.percent);
              if(me._curStep == me._numSteps)
                return;
            } else {
              me._masterProgress.update({
                maximum: 100,
                progress: data.percent,
                indeterminate: false
              });
              me._masterProgress(data.percent);
            }
          } else {
            me._masterProgress.update({'indeterminate': true});
          }
          setTimeout(function() {
            me.update();
          }, 1000);
        });
      } else {
        xhr.get(me.poolUrl, {
          headers: {"X-Progress-ID": me.uuid},
          handleAs: "json"
        }).then(function(data) {
          if(data.step) {
            me._curStep = data.step;
          }
          if(data.percent) {
            if(data.percent == 100) {
              me._subProgress.update({'indeterminate': true});
              me._masterProgress(data.percent);
              if(me._curStep == me._numSteps)
                return;
            } else {
              me._subProgress.update({
                maximum: 100,
                progress: data.percent,
                indeterminate: false
              });
              me._masterProgress(data.percent);
            }
          } else {
            me._masterProgress(0);
            me._subProgress.update({'indeterminate': true});
          }
          setTimeout(function() {
            me.update();
          }, 1000);
        });
      }
    },
    destroy: function() {
      //this.timer.stop();
      this.inherited(arguments);
    },
    onFinished: function() {
    }
  });
  return Progress;
});
