define([
	"dojo/node!wd/lib/special-keys"
], function (specialKeys) {
	return {
		isShiftClickSupported: function (remote) {
			// summary:
			//		Detects browser/WebDriver support of shift+click.
			//		This is known to not work in many versions of IE & FF with
			//		Selenium's drivers.
			// remote: PromisedWebDriver
			//		A webdriver instance with a remote page already loaded
			// returns:
			//		A promise that resolves to a boolean

			remote.execute(function () {
				window.shiftClickTestButtonClicked = false;
				window.isShiftClickSupported = false;
				var button = document.createElement("button");
				button.id = "shiftClickTestButton";
				button.onclick = function (event) {
					window.shiftClickTestButtonClicked = true;
					window.isShiftClickSupported = event.shiftKey;
				};
				document.body.appendChild(button);
			});
			
			remote.keys(specialKeys.Shift)
				.elementById("shiftClickTestButton")
				.clickElement()
				.keys(specialKeys.NULL)
				.end()
				.waitForCondition("shiftClickTestButtonClicked", 5000);
			
			return remote.execute(function () {
				document.body.removeChild(document.getElementById('shiftClickTestButton'));
				return window.isShiftClickSupported;
			});
		},
		
		isInputHomeEndSupported: function (remote) {
			// summary:
			//		Detects whether the given browser/OS combination supports
			//		using the home and end keys to move the caret in a textbox.
			// remote: PromisedWebDriver
			//		A webdriver instance with a remote page already loaded
			// returns:
			//		A promise that resolves to a boolean
			
			remote.execute(function () {
				var input = document.createElement("input");
				input.id = "homeEndTestInput";
				input.value = "2";
				document.body.appendChild(input);
			});
			
			remote.elementById("homeEndTestInput")
				.clickElement()
				.type(specialKeys.End + "3" + specialKeys.Home + "1")
				.end();
			
			return remote.execute(function () {
				var input = document.getElementById("homeEndTestInput"),
					value = input.value;
				document.body.removeChild(input);
				return value === "123";
			});
		}
	};
});
