webshell = (function() {

    var cls = function(id,width,height,handler) {
        var sid=""+Math.round(Math.random()*1000000000);
        var kb=[];
        var isactive=false;
        this.islocked=false;
        var qtimer;
        var qtime=100;
        var retry=0;
        var cy=0;
        var div=dojo.byId(id);
        var me = this;

        this.update = function() {

            if(!me.islocked) {
                me.islocked=true;
                var send="";
                while(kb.length>0)
                    send+=kb.pop();
                dojo.xhrGet({
                    url: "/system/terminal/",
                    content: {s: sid, w: width, h: height, k: send},
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    sync: false,
                    preventCache: true,
                    handleAs: 'text',
                    handle: function(data, req) {
                        me.islocked=false;
                        if (!isactive) {
                            isactive=true;
                            handler('conn',0);
                        }
                        if(req.xhr.status==200) {
                            retry=0;
                            cy=data.substring(45,48);
                            html=data.substring(52);
                            if(html.length>0) {
                                div.innerHTML=html;
                                handler('curs',cy);
                                qtime=100;
                            } else {
                                qtime*=2;
                                if(qtime>2000)
                                    qtime=2000;
                            }
                            qtimer=window.setTimeout(me.update,qtime);
                        } else if (req.xhr.status==400)
                            handler('disc',0);
                        else {
                            retry++;
                            if (retry<3)
                                qtimer=window.setTimeout(me.update,2000);
                            else
                                handler('disc',1);
                        }
                    },
                });

            }
        }
        function queue(s) {
            kb.unshift(s);
            qtime=100;
            if(!me.islocked) {
                window.clearTimeout(qtimer);
                qtimer=window.setTimeout(me.update,1);
            }
        }
        function private_sendkey(kc) {
            var k="";
            // Build character
            switch(kc) {
            case 126:k="~~";break;
            case 63232:k="~A";break;// Up
            case 63233:k="~B";break;// Down
            case 63234:k="~D";break;// Left
            case 63235:k="~C";break;// Right
            case 63276:k="~1";break;// PgUp
            case 63277:k="~2";break;// PgDn
            case 63273:k="~H";break;// Home
            case 63275:k="~F";break;// End
            case 63302:k="~3";break;// Ins
            case 63272:k="~4";break;// Del
            case 63236:k="~a";break;// F1
            case 63237:k="~b";break;// F2
            case 63238:k="~c";break;// F3
            case 63239:k="~d";break;// F4
            case 63240:k="~e";break;// F5
            case 63241:k="~f";break;// F6
            case 63242:k="~g";break;// F7
            case 63243:k="~h";break;// F8
            case 63244:k="~i";break;// F9
            case 63245:k="~j";break;// F10
            case 63246:k="~k";break;// F11
            case 63247:k="~l";break;// F12
            default:k=String.fromCharCode(kc);
            }
            queue(k);
        };
        this.sendkey = function(kc) {
            private_sendkey(kc);
        }
        this.keypress = function(ev) {
            // Translate to standard keycodes
            if (!ev) var ev=window.event;
            var kc;

            if (ev.keyCode) kc=ev.keyCode;
            if (ev.which) kc=ev.which;
            if (ev.ctrlKey) {
                if (kc>=0 && kc<=32) kc=kc;
                else if (kc>=65 && kc<=90) kc-=64;
                else if (kc>=97 && kc<=122) kc-=96;
                else {
                    switch (kc) {
                    case 54:kc=30;break;    // Ctrl-^
                    case 109:kc=31;break;    // Ctrl-_
                    case 219:kc=27;break;    // Ctrl-[
                    case 220:kc=28;break;    // Ctrl-\
                    case 221:kc=29;break;    // Ctrl-]
                    default: return true;
                    }
                }
            } else if (ev.which==0) {
                switch(kc) {
                case 8: break;            // Backspace
                case 27: break;            // ESC
                case 33:kc=63276;break;    // PgUp
                case 34:kc=63277;break;    // PgDn
                case 35:kc=63275;break;    // End
                case 36:kc=63273;break;    // Home
                case 37:kc=63234;break;    // Left
                case 38:kc=63232;break;    // Up
                case 39:kc=63235;break;    // Right
                case 40:kc=63233;break;    // Down
                case 45:kc=63302;break;    // Ins
                case 46:kc=63272;break;    // Del
                case 112:kc=63236;break;// F1
                case 113:kc=63237;break;// F2
                case 114:kc=63238;break;// F3
                case 115:kc=63239;break;// F4
                case 116:kc=63240;break;// F5
                case 117:kc=63241;break;// F6
                case 118:kc=63242;break;// F7
                case 119:kc=63243;break;// F8
                case 120:kc=63244;break;// F9
                case 121:kc=63245;break;// F10
                case 122:kc=63246;break;// F11
                case 123:kc=63247;break;// F12
                default: return true;
                }
            }
            if(kc==8) kc=127;
            private_sendkey(kc);

            ev.cancelBubble=true;
            if (ev.stopPropagation) ev.stopPropagation();
            if (ev.preventDefault) ev.preventDefault();

            return true;
        }
        this.keydown = function(ev) {
            if (!ev) var ev=window.event;
            if (dojo.isIE) {
                o={9:1,8:1,27:1,33:1,34:1,35:1,36:1,37:1,38:1,39:1,40:1,45:1,46:1,112:1,
                    113:1,114:1,115:1,116:1,117:1,118:1,119:1,120:1,121:1,122:1,123:1};
                if (o[ev.keyCode] || ev.ctrlKey || ev.altKey) {
                    ev.which=0;
                    return keypress(ev);
                }
            }
        }
        qtimer=window.setTimeout(me.update, 1);
    }

    return cls;

})();
