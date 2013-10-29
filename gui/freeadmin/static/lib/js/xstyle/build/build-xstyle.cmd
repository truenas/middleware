cat core/amdLoader.js ../put-selector/put.js core/elemental.js core/ruleModel.js core/parser.js main.js > xstyle.js
uglifyjs xstyle.js -o xstyle.min.js --source-map xstyle.min.js.map -p 2 -c -m