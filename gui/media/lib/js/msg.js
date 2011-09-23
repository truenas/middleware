/*-
 * Copyright (c) 2011 iXsystems, Inc.
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
 * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
 * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
 * SUCH DAMAGE.
 *
 */

dojo.require('dojox.timing');
t = new dojox.timing.Timer(1000);
var _msgstarted = false;

loadlog = function(load) {
    if(dijit.byId("stopmsgrefresh").get("value") == "on" || _msgstarted == true)
        return;
    _msgstarted = true;
    var msgfull = dijit.byId('log_dialog');
    url = msgfull.open? '/system/varlogmessages/500/' : '/system/varlogmessages/';
    dojo.xhrGet({
    url: url,
    handleAs: "xml",
    load: function(data) {
        _msgstarted = false;
        var msgOutput = data.getElementsByTagName('msg')[0].childNodes[0].nodeValue;
        var pageElement = dojo.byId(msgfull.open? 'msgfull_output' : 'msg_output');
        var newinterval = 1000;
        var saved_delta;

        if (msgOutput != pageElement.innerHTML) {
            if (msgfull.open)
                saved_delta = pageElement.scrollHeight - pageElement.scrollTop - 400;
            if ('innerText' in pageElement) {
                pageElement.innerText = msgOutput;
            } else { 
                pageElement.innerHTML = msgOutput;
            }
            if (t.interval > 1250) {
                newinterval = t.interval / 3;
                if (newinterval < 1250)
                newinterval = 1250;
                t.setInterval(newinterval);
            }

            if (msgfull.open && (saved_delta < 32))
                pageElement.scrollTop = pageElement.scrollHeight;
        } else if (t.interval < 7500) {
            newinterval = t.interval * 5 / 3;
            if (newinterval > 7500)
                newinterval = 7500;
            t.setInterval(newinterval);
        }
        if (load && msgfull.open)
            pageElement.scrollTop = pageElement.scrollHeight;
    },
    });
}

t.onTick = function() {
    loadlog(false);
}
t.onStart = function() {
    loadlog(false);
}

dojo.addOnLoad(function() {
    t.start();
});
