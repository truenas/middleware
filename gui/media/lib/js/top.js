/*-
 * Copyright (c) 2011 iXsystems, Inc.
 * All rights reserved.
 *
 * Written by:	Xin LI
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

var oReq = false; // XMLHttpRequest Object
var hInterval = -1;
var resURL = '/system/top/';

/*
 * Callback handler for readystatechange
 */
function _cbStateChange() {
	if (oReq.readyState==4) {
		if (oReq.responseText.toLowerCase() != 'invalid') {
			var xmlTree = oReq.responseXML;
			//var topOutput = xmlTree.documentElement.getElementsByTagName('top').item(0).firstChild.data;
			var topOutput = xmlTree.childNodes[0].childNodes[0].wholeText;
			var pageElement = document.getElementById('top_output');

            var top_dialog = dijit.byId("top_dialog");
            if(!top_dialog.open) {
                _StopTopOutput();
            }

			pageElement.innerHTML = topOutput;
		}
	}
}

/*
 * Callout to request top output from server
 */
function _cbSyncTopOutput() {
	try {
		oReq.open("GET", resURL, true);
		oReq.onreadystatechange = _cbStateChange;
		oReq.send(null);
	} catch (e) {
		;
	}
}

/*
 * Initialize the refresher
 */
function _InitTopOutput() {
	if (window.XMLHttpRequest) {
		oReq = new XMLHttpRequest();
	} else if (window.ActiveXObject) {
		oReq = new ActiveXObject("Microsoft.XMLHTTP");
	}

	/* Load output immediately */
	_cbSyncTopOutput();

	/* Setup future updates at 2.5s rate */
	if (hInterval == -1)
		hInterval = window.setInterval("_cbSyncTopOutput()", 2500);
}

/*
 * Stop the refresher
 */
function _StopTopOutput() {
	if (hInterval != -1) {
		window.clearInterval(hInterval);
		hInterval = -1;
	}
}
