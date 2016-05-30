define({
	// The port on which the instrumenting proxy will listen
	proxyPort: 9000,

	// A fully qualified URL to the Intern proxy
	proxyUrl: 'http://localhost:9000/',

	// Default desired capabilities for all environments. Individual capabilities can be overridden by any of the
	// specified browser environments in the `environments` array below as well. See
	// https://code.google.com/p/selenium/wiki/DesiredCapabilities for standard Selenium capabilities and
	// https://saucelabs.com/docs/additional-config#desired-capabilities for Sauce Labs capabilities.
	// Note that the `build` capability will be filled in with the current commit ID from the Travis CI environment
	// automatically
	capabilities: {
		// Limit duration of each job to avoid waste of resources during hangs
		'max-duration': 600,
		// Increase timeout if Sauce Labs receives no new commands
		// (no commands are sent during non-functional unit tests)
		'idle-timeout': 180,
		// Specify Selenium version (the default is several versions old)
		'selenium-version': '2.39.0'
	},

	// Browsers to run integration testing against. Note that version numbers must be strings if used with Sauce
	// OnDemand. Options that will be permutated are browserName, version, platform, and platformVersion; any other
	// capabilities options specified for an environment will be copied as-is
	environments: [
		{ browserName: 'internet explorer', version: '11', platform: 'Windows 8.1' },
		{ browserName: 'internet explorer', version: '10', platform: 'Windows 8' },
		{ browserName: 'internet explorer', version: '9', platform: 'Windows 7' },
		{ browserName: 'firefox', platform: [ 'Linux', 'OS X 10.6', 'Windows 7' ] },
		{ browserName: 'chrome', platform: [ 'Linux', 'OS X 10.8', 'Windows 7' ] },
		{ browserName: 'safari', version: '6', platform: 'OS X 10.8' }
	],

	// Maximum number of simultaneous integration tests that should be executed on the remote WebDriver service
	maxConcurrency: 3,

	// Whether or not to start Sauce Connect before running tests
	useSauceConnect: true,

	// Connection information for the remote WebDriver service. If using Sauce Labs, keep your username and password
	// in the SAUCE_USERNAME and SAUCE_ACCESS_KEY environment variables unless you are sure you will NEVER be
	// publishing this configuration file somewhere
	webdriver: {
		host: 'localhost',
		port: 4444
	},

	// Configuration options for the module loader; any AMD configuration options supported by the Dojo loader can be
	// used here
	loader: {
		baseUrl: typeof process === 'undefined' ?
				// if we are using the full path to xstyle, we assume we are running
				// in a sibling path configuration
				location.search.indexOf('config=xstyle') > -1 ? '../..' : '..' :
			'./node_modules',

		// Packages that should be registered with the loader in each testing environment
		requestProvider: 'dojo/request/registry',
		packages: [
			{ name: 'dojo', location: 'dojo' },
			{ name: 'put-selector', location: 'put-selector' },
			{
				name: 'xstyle',
				location: typeof process === 'undefined' ?
					location.search.indexOf('config=xstyle') > -1 ? 'xstyle' : '..' :
					'..'
			}
		]
	},

	// A regular expression matching URLs to files that should not be included in code coverage analysis
	excludeInstrumentation: /^dojox?|^dijit|^put-selector|\/test\/|\/nls\//,

	// Non-functional test suite(s) to run in each browser
	suites: [ 'xstyle/test/all' ],

	// Functional test suite(s) to run in each browser once non-functional tests are completed
	functionalSuites: []
});