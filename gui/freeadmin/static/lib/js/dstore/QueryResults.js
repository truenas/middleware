define(['dojo/_base/lang', 'dojo/when'], function (lang, when) {
	function forEach(callback, instance) {
		return when(this, function(data) {
			for (var i = 0, l = data.length; i < l; i++){
				callback.call(instance, data[i], i, data);
			}
		});
	}
	return function (data, options) {
		var hasTotalLength = options && 'totalLength' in options;
		if(data.then) {
			data = lang.delegate(data);
			// a promise for the eventual realization of the totalLength, in
			// case it comes from the resolved data
			var totalLengthPromise = data.then(function (data) {
				// calculate total length, now that we have access to the resolved data
				var totalLength = hasTotalLength ? options.totalLength :
						data.totalLength || data.length;
				// make it available on the resolved data
				data.totalLength = totalLength;
				// don't return the totalLength promise unless we need to, to avoid
				// triggering a lazy promise
				return !hasTotalLength && totalLength;
			});
			// make the totalLength available on the promise (whether through the options or the enventual
			// access to the resolved data)
			data.totalLength = hasTotalLength ? options.totalLength : totalLengthPromise;
			// make the response available as well
			data.response = options && options.response;
		} else {
			data.totalLength = hasTotalLength ? options.totalLength : data.length;
		}

		data.forEach = forEach;

		return data;
	};
});
