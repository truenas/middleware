# Testing

dstore uses [Intern](http://theintern.io/) as its test runner. Tests can
either be run using the browser, or using [Sauce Labs](https://saucelabs.com/).
More information on writing your own tests with Intern can be found in the
[Intern wiki](https://github.com/theintern/intern/wiki).

## Setting up

**Note:** Commands listed in this section are all written assuming they are
run in the `dstore` directory.

Install dependencies for testing.

```
npm install 
```

## Running via the browser

1. Open a browser to http://hostname/path_to_dstore/tests/runTests.html
2. View the console

## Running in the console

Run the tests with the following command:

```
node node_modules/intern-geezer/client config=tests/intern
```

## Running via Sauce Labs

Make sure the proper Sauce Labs credentials are set in the environment:

```
export SAUCE_USERNAME=<your_sauce_username>
export SAUCE_ACCESS_KEY=<your_sauce_access_key>
```

Then kick off the runner with the following command:

```
node node_modules/intern-geezer/runner config=tests/intern
```
