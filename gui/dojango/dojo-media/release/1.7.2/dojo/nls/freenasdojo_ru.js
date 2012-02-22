require({cache:{
'dojox/form/nls/ru/CheckedMultiSelect':function(){
define(
"dojox/form/nls/ru/CheckedMultiSelect", ({
	invalidMessage: "Необходимо выбрать, как минимум, один элемент.",
	multiSelectLabelText: "Выбрано элементов: {num}"
})
);

},
'dijit/nls/ru/common':function(){
define(
"dijit/nls/ru/common", //begin v1.x content
({
	buttonOk: "ОК",
	buttonCancel: "Отмена",
	buttonSave: "Сохранить",
	itemClose: "Закрыть"
})
//end v1.x content
);

},
'dojox/grid/enhanced/nls/ru/Filter':function(){
define(
"dojox/grid/enhanced/nls/ru/Filter", //begin v1.x content
({
	"clearFilterDialogTitle": "Удалить фильтр",
	"filterDefDialogTitle": "Фильтр",
	"ruleTitleTemplate": "Правило ${0}",
	
	"conditionEqual": "равно",
	"conditionNotEqual": "не равно",
	"conditionLess": "меньше, чем",
	"conditionLessEqual": "меньше или равно",
	"conditionLarger": "больше, чем",
	"conditionLargerEqual": "больше или равно",
	"conditionContains": "содержит",
	"conditionIs": "является",
	"conditionStartsWith": "начинается с",
	"conditionEndWith": "заканчивается на",
	"conditionNotContain": "не содержит",
	"conditionIsNot": "не является",
	"conditionNotStartWith": "не начинается с",
	"conditionNotEndWith": "не заканчивается на",
	"conditionBefore": "до",
	"conditionAfter": "после",
	"conditionRange": "диапазон",
	"conditionIsEmpty": "пустое",
	
	"all": "все",
	"any": "любое",
	"relationAll": "все правила",
	"waiRelAll": "Соответствие всем следующим правилам:",
	"relationAny": "любое правило",
	"waiRelAny": "Соответствие любому из следующих правил:",
	"relationMsgFront": "Соответствие",
	"relationMsgTail": "",
	"and": "и",
	"or": "или",
	
	"addRuleButton": "Добавить правило",
	"waiAddRuleButton": "Добавить новое правило",
	"removeRuleButton": "Удалить правило",
	"waiRemoveRuleButtonTemplate": "Удалить правило ${0}",
	
	"cancelButton": "Отмена",
	"waiCancelButton": "Отменить этот диалог",
	"clearButton": "Удалить",
	"waiClearButton": "Удалить фильтр",
	"filterButton": "Фильтр",
	"waiFilterButton": "Передать фильтр",
	
	"columnSelectLabel": "Столбец",
	"waiColumnSelectTemplate": "Столбец для правила ${0}",
	"conditionSelectLabel": "Условие",
	"waiConditionSelectTemplate": "Условие для правила ${0}",
	"valueBoxLabel": "Значение",
	"waiValueBoxTemplate": "Задайте значение фильтра для правила ${0}",
	
	"rangeTo": "до",
	"rangeTemplate": "от ${0} до ${1}",
	
	"statusTipHeaderColumn": "Столбец",
	"statusTipHeaderCondition": "Правила",
	"statusTipTitle": "Панель фильтра",
	"statusTipMsg": "Щелкните по панели фильтра, чтобы применить фильтр к значениям в ${0}.",
	"anycolumn": "любой столбец",
	"statusTipTitleNoFilter": "Панель фильтра",
	"statusTipTitleHasFilter": "Фильтр",
	"statusTipRelAny": "Соответствует любому из правил.",
	"statusTipRelAll": "Соответствует всем правилам.",
	
	"defaultItemsName": "элементов",
	"filterBarMsgHasFilterTemplate": "Показано ${0} из ${1} ${2}.",
	"filterBarMsgNoFilterTemplate": "Фильтр не применен",
	
	"filterBarDefButton": "Задать фильтр",
	"waiFilterBarDefButton": "Применить фильтр к таблице",
	"a11yFilterBarDefButton": "Фильтр...",
	"filterBarClearButton": "Удалить фильтр",
	"waiFilterBarClearButton": "Удалить фильтр",
	"closeFilterBarBtn": "Закрыть панель фильтра",
	
	"clearFilterMsg": "Фильтр будет удален, и будут показаны все записи.",
	"anyColumnOption": "Любой столбец",
	
	"trueLabel": "True",
	"falseLabel": "False"
})
//end v1.x content
);

},
'dojo/cldr/nls/ru/gregorian':function(){
define(
"dojo/cldr/nls/ru/gregorian", //begin v1.x content
{
	"dateFormatItem-yM": "M.y",
	"field-dayperiod": "AM/PM",
	"field-minute": "Минута",
	"eraNames": [
		"до н.э.",
		"н.э."
	],
	"dateFormatItem-MMMEd": "ccc, d MMM",
	"field-day-relative+-1": "Вчера",
	"field-weekday": "День недели",
	"dateFormatItem-yQQQ": "y QQQ",
	"field-day-relative+-2": "Позавчера",
	"dateFormatItem-MMdd": "dd.MM",
	"days-standAlone-wide": [
		"Воскресенье",
		"Понедельник",
		"Вторник",
		"Среда",
		"Четверг",
		"Пятница",
		"Суббота"
	],
	"dateFormatItem-MMM": "LLL",
	"months-standAlone-narrow": [
		"Я",
		"Ф",
		"М",
		"А",
		"М",
		"И",
		"И",
		"А",
		"С",
		"О",
		"Н",
		"Д"
	],
	"field-era": "Эра",
	"field-hour": "Час",
	"quarters-standAlone-abbr": [
		"1-й кв.",
		"2-й кв.",
		"3-й кв.",
		"4-й кв."
	],
	"dateFormatItem-yyMMMEEEd": "EEE, d MMM yy",
	"dateFormatItem-y": "y",
	"timeFormat-full": "H:mm:ss zzzz",
	"dateFormatItem-yyyy": "y",
	"months-standAlone-abbr": [
		"янв.",
		"февр.",
		"март",
		"апр.",
		"май",
		"июнь",
		"июль",
		"авг.",
		"сент.",
		"окт.",
		"нояб.",
		"дек."
	],
	"dateFormatItem-Ed": "E, d",
	"dateFormatItem-yMMM": "LLL y",
	"field-day-relative+0": "Сегодня",
	"dateFormatItem-yyyyLLLL": "LLLL y",
	"field-day-relative+1": "Завтра",
	"days-standAlone-narrow": [
		"В",
		"П",
		"В",
		"С",
		"Ч",
		"П",
		"С"
	],
	"eraAbbr": [
		"до н.э.",
		"н.э."
	],
	"field-day-relative+2": "Послезавтра",
	"dateFormatItem-yyyyMM": "MM.yyyy",
	"dateFormatItem-yyyyMMMM": "LLLL y",
	"dateFormat-long": "d MMMM y 'г'.",
	"timeFormat-medium": "H:mm:ss",
	"field-zone": "Часовой пояс",
	"dateFormatItem-Hm": "H:mm",
	"dateFormat-medium": "dd.MM.yyyy",
	"dateFormatItem-yyMM": "MM.yy",
	"dateFormatItem-Hms": "H:mm:ss",
	"dateFormatItem-yyMMM": "LLL yy",
	"quarters-standAlone-wide": [
		"1-й квартал",
		"2-й квартал",
		"3-й квартал",
		"4-й квартал"
	],
	"dateFormatItem-ms": "mm:ss",
	"dateFormatItem-yyyyQQQQ": "QQQQ y 'г'.",
	"field-year": "Год",
	"months-standAlone-wide": [
		"Январь",
		"Февраль",
		"Март",
		"Апрель",
		"Май",
		"Июнь",
		"Июль",
		"Август",
		"Сентябрь",
		"Октябрь",
		"Ноябрь",
		"Декабрь"
	],
	"field-week": "Неделя",
	"dateFormatItem-MMMd": "d MMM",
	"dateFormatItem-yyQ": "Q yy",
	"timeFormat-long": "H:mm:ss z",
	"months-format-abbr": [
		"янв.",
		"февр.",
		"марта",
		"апр.",
		"мая",
		"июня",
		"июля",
		"авг.",
		"сент.",
		"окт.",
		"нояб.",
		"дек."
	],
	"timeFormat-short": "H:mm",
	"dateFormatItem-H": "H",
	"field-month": "Месяц",
	"quarters-format-abbr": [
		"1-й кв.",
		"2-й кв.",
		"3-й кв.",
		"4-й кв."
	],
	"days-format-abbr": [
		"вс",
		"пн",
		"вт",
		"ср",
		"чт",
		"пт",
		"сб"
	],
	"dateFormatItem-M": "L",
	"days-format-narrow": [
		"В",
		"П",
		"В",
		"С",
		"Ч",
		"П",
		"С"
	],
	"field-second": "Секунда",
	"field-day": "День",
	"dateFormatItem-MEd": "E, d.M",
	"months-format-narrow": [
		"Я",
		"Ф",
		"М",
		"А",
		"М",
		"И",
		"И",
		"А",
		"С",
		"О",
		"Н",
		"Д"
	],
	"days-standAlone-abbr": [
		"Вс",
		"Пн",
		"Вт",
		"Ср",
		"Чт",
		"Пт",
		"Сб"
	],
	"dateFormat-short": "dd.MM.yy",
	"dateFormatItem-yMMMEd": "E, d MMM y",
	"dateFormat-full": "EEEE, d MMMM y 'г'.",
	"dateFormatItem-Md": "d.M",
	"dateFormatItem-yMEd": "EEE, d.M.y",
	"months-format-wide": [
		"января",
		"февраля",
		"марта",
		"апреля",
		"мая",
		"июня",
		"июля",
		"августа",
		"сентября",
		"октября",
		"ноября",
		"декабря"
	],
	"dateFormatItem-d": "d",
	"quarters-format-wide": [
		"1-й квартал",
		"2-й квартал",
		"3-й квартал",
		"4-й квартал"
	],
	"days-format-wide": [
		"воскресенье",
		"понедельник",
		"вторник",
		"среда",
		"четверг",
		"пятница",
		"суббота"
	],
	"eraNarrow": [
		"до н.э.",
		"н.э."
	]
}
//end v1.x content
);
},
'dojo/cldr/nls/ru/number':function(){
define(
"dojo/cldr/nls/ru/number", //begin v1.x content
{
	"group": " ",
	"percentSign": "%",
	"exponential": "E",
	"scientificFormat": "#E0",
	"percentFormat": "#,##0 %",
	"list": ";",
	"infinity": "∞",
	"patternDigit": "#",
	"minusSign": "-",
	"decimal": ",",
	"nativeZeroDigit": "0",
	"perMille": "‰",
	"decimalFormat": "#,##0.###",
	"currencyFormat": "#,##0.00 ¤",
	"plusSign": "+"
}
//end v1.x content
);
},
'dojox/grid/enhanced/nls/ru/EnhancedGrid':function(){
define(
"dojox/grid/enhanced/nls/ru/EnhancedGrid", //begin v1.x content
({
	singleSort: "Простая сортировка",
	nestedSort: "Вложенная сортировка",
	ascending: "По возрастанию",
	descending: "По убыванию",
	sortingState: "${0} - ${1}",
	unsorted: "Не сортировать этот столбец",
	indirectSelectionRadio: "Строка ${0}, один выбор, радиокнопка",
	indirectSelectionCheckBox: "Строка ${0}, несколько выборов, переключатель",
	selectAll: "Выбрать все"
})
//end v1.x content
);


},
'dijit/_editor/nls/ru/commands':function(){
define(
"dijit/_editor/nls/ru/commands", //begin v1.x content
({
	'bold': 'Полужирный',
	'copy': 'Копировать',
	'cut': 'Вырезать',
	'delete': 'Удалить',
	'indent': 'Отступ',
	'insertHorizontalRule': 'Горизонтальная линейка',
	'insertOrderedList': 'Нумерованный список',
	'insertUnorderedList': 'Список с маркерами',
	'italic': 'Курсив',
	'justifyCenter': 'По центру',
	'justifyFull': 'По ширине',
	'justifyLeft': 'По левому краю',
	'justifyRight': 'По правому краю',
	'outdent': 'Втяжка',
	'paste': 'Вставить',
	'redo': 'Повторить',
	'removeFormat': 'Удалить формат',
	'selectAll': 'Выбрать все',
	'strikethrough': 'Перечеркивание',
	'subscript': 'Нижний индекс',
	'superscript': 'Верхний индекс',
	'underline': 'Подчеркивание',
	'undo': 'Отменить',
	'unlink': 'Удалить ссылку',
	'createLink': 'Создать ссылку',
	'toggleDir': 'Изменить направление',
	'insertImage': 'Вставить изображение',
	'insertTable': 'Вставить/изменить таблицу',
	'toggleTableBorder': 'Переключить рамку таблицы',
	'deleteTable': 'Удалить таблицу',
	'tableProp': 'Свойства таблицы',
	'htmlToggle': 'Код HTML',
	'foreColor': 'Цвет текста',
	'hiliteColor': 'Цвет фона',
	'plainFormatBlock': 'Стиль абзаца',
	'formatBlock': 'Стиль абзаца',
	'fontSize': 'Размер шрифта',
	'fontName': 'Название шрифта',
	'tabIndent': 'Табуляция',
	"fullScreen": "Переключить полноэкранный режим",
	"viewSource": "Показать исходный код HTML",
	"print": "Печать",
	"newPage": "Создать страницу",
	/* Error messages */
	'systemShortcut': 'Действие "${0}" можно выполнить в браузере только путем нажатия клавиш ${1}.'
})

//end v1.x content
);

},
'dojox/grid/enhanced/nls/ru/Pagination':function(){
define(
"dojox/grid/enhanced/nls/ru/Pagination", //begin v1.x content
({
	"descTemplate": "${2} - ${3} из ${1} ${0}",
	"firstTip": "Первая страница",
	"lastTip": "Последняя страница",
	"nextTip": "Следующая страница",
	"prevTip": "Предыдущая страница",
	"itemTitle": "элементов",
	"singularItemTitle": "элемент",
	"pageStepLabelTemplate": "Страница ${0}",
	"pageSizeLabelTemplate": "${0} элементов на странице",
	"allItemsLabelTemplate": "Все элементы",
	"gotoButtonTitle": "Перейти на определенную страницу",
	"dialogTitle": "Перейти на страницу",
	"dialogIndication": "Задайте номер страницы",
	"pageCountIndication": " (${0} страниц)",
	"dialogConfirm": "Перейти",
	"dialogCancel": "Отмена",
	"all": "все"
})
//end v1.x content
);


},
'dijit/form/nls/ru/validate':function(){
define(
"dijit/form/nls/ru/validate", //begin v1.x content
({
	invalidMessage: "Указано недопустимое значение.",
	missingMessage: "Это обязательное значение.",
	rangeMessage: "Это значение вне диапазона."
})
//end v1.x content
);

},
'dojo/cldr/nls/ru/currency':function(){
define(
"dojo/cldr/nls/ru/currency", //begin v1.x content
{
	"HKD_displayName": "Гонконгский доллар",
	"CHF_displayName": "Швейцарский франк",
	"CAD_displayName": "Канадский доллар",
	"CNY_displayName": "Юань Ренминби",
	"USD_symbol": "$",
	"AUD_displayName": "Австралийский доллар",
	"JPY_displayName": "Японская иена",
	"USD_displayName": "Доллар США",
	"GBP_displayName": "Английский фунт стерлингов",
	"EUR_displayName": "Евро"
}
//end v1.x content
);
},
'dijit/form/nls/ru/ComboBox':function(){
define(
"dijit/form/nls/ru/ComboBox", //begin v1.x content
({
		previousMessage: "Предыдущие варианты",
		nextMessage: "Следующие варианты"
})
//end v1.x content
);

},
'dijit/nls/ru/loading':function(){
define(
"dijit/nls/ru/loading", //begin v1.x content
({
	loadingState: "Загрузка...",
	errorState: "Извините, возникла ошибка"
})
//end v1.x content
);

}}});
define("dojo/nls/freenasdojo_ru", [], 1);
