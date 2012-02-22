require({cache:{
'dojox/form/nls/el/CheckedMultiSelect':function(){
define(
"dojox/form/nls/el/CheckedMultiSelect", ({
	invalidMessage: "Πρέπει να επιλέξετε τουλάχιστον ένα στοιχείο.",
	multiSelectLabelText: "Επιλέχθηκε(-αν) {num} στοιχείο(-α)"
})
);

},
'dijit/nls/el/common':function(){
define(
"dijit/nls/el/common", //begin v1.x content
({
	buttonOk: "ΟΚ",
	buttonCancel: "Ακύρωση",
	buttonSave: "Αποθήκευση",
	itemClose: "Κλείσιμο"
})
//end v1.x content
);

},
'dojox/grid/enhanced/nls/el/Filter':function(){
define(
"dojox/grid/enhanced/nls/el/Filter", //begin v1.x content
({
	"clearFilterDialogTitle": "Εκκαθάριση φίλτρου",
	"filterDefDialogTitle": "Φίλτρο",
	"ruleTitleTemplate": "Κανόνας ${0}",
	
	"conditionEqual": "ίσο",
	"conditionNotEqual": "όχι ίσο",
	"conditionLess": "είναι μικρότερο από",
	"conditionLessEqual": "μικρότερο ή ίσο",
	"conditionLarger": "είναι μεγαλύτερο από",
	"conditionLargerEqual": "μεγαλύτερο ή ίσο",
	"conditionContains": "περιέχει",
	"conditionIs": "είναι",
	"conditionStartsWith": "αρχίζει από",
	"conditionEndWith": "τελειώνει σε",
	"conditionNotContain": "δεν περιέχει",
	"conditionIsNot": "δεν είναι",
	"conditionNotStartWith": "δεν αρχίζει από",
	"conditionNotEndWith": "δεν τελειώνει σε",
	"conditionBefore": "πριν",
	"conditionAfter": "μετά",
	"conditionRange": "εύρος",
	"conditionIsEmpty": "είναι κενό",
	
	"all": "όλα",
	"any": "οποιοδήποτε",
	"relationAll": "όλοι οι κανόνες",
	"waiRelAll": "Αντιστοιχία με όλους τους παρακάτω κανόνες:",
	"relationAny": "οποιοσδήποτε κανόνας",
	"waiRelAny": "Αντιστοιχία με οποιονδήποτε από τους παρακάτω κανόνες:",
	"relationMsgFront": "Αντιστοιχία",
	"relationMsgTail": "",
	"and": "και",
	"or": "ή",
	
	"addRuleButton": "Προσθήκη κανόνα",
	"waiAddRuleButton": "Προσθήκη νέου κανόνα",
	"removeRuleButton": "Αφαίρεση κανόνα",
	"waiRemoveRuleButtonTemplate": "Αφαίρεση κανόνα ${0}",
	
	"cancelButton": "Ακύρωση",
	"waiCancelButton": "Ακύρωση αυτού του πλαισίου διαλόγου",
	"clearButton": "Εκκαθάριση",
	"waiClearButton": "Εκκαθάριση του φίλτρου",
	"filterButton": "Φίλτρο",
	"waiFilterButton": "Υποβολή του φίλτρου",
	
	"columnSelectLabel": "Στήλη",
	"waiColumnSelectTemplate": "Στήλη για τον κανόνα ${0}",
	"conditionSelectLabel": "Συνθήκη",
	"waiConditionSelectTemplate": "Συνθήκη για τον κανόνα ${0}",
	"valueBoxLabel": "Τιμή",
	"waiValueBoxTemplate": "Καταχωρήστε τιμή φίλτρου για τον κανόνα ${0}",
	
	"rangeTo": "έως",
	"rangeTemplate": "από ${0} έως ${1}",
	
	"statusTipHeaderColumn": "Στήλη",
	"statusTipHeaderCondition": "Κανόνες",
	"statusTipTitle": "Γραμμή φίλτρου",
	"statusTipMsg": "Πατήστε στη γραμμή φίλτρου για φιλτράρισμα με βάση τις τιμές στο ${0}.",
	"anycolumn": "οποιαδήποτε στήλη",
	"statusTipTitleNoFilter": "Γραμμή φίλτρου",
	"statusTipTitleHasFilter": "Φίλτρο",
	"statusTipRelAny": "Αντιστοιχία με οποιουσδήποτε κανόνες.",
	"statusTipRelAll": "Αντιστοιχία με όλους τους κανόνες.",
	
	"defaultItemsName": "στοιχεία",
	"filterBarMsgHasFilterTemplate": "Εμφανίζονται ${0} από ${1} ${2}.",
	"filterBarMsgNoFilterTemplate": "Δεν έχει εφαρμοστεί φίλτρο",
	
	"filterBarDefButton": "Ορισμός φίλτρου",
	"waiFilterBarDefButton": "Φιλτράρισμα του πίνακα",
	"a11yFilterBarDefButton": "Φιλτράρισμα...",
	"filterBarClearButton": "Εκκαθάριση φίλτρου",
	"waiFilterBarClearButton": "Εκκαθάριση του φίλτρου",
	"closeFilterBarBtn": "Κλείσιμο γραμμής φίλτρου",
	
	"clearFilterMsg": "Με την επιλογή αυτή θα αφαιρεθεί το φίλτρο και θα εμφανιστούν όλες οι διαθέσιμες εγγραφές.",
	"anyColumnOption": "Οποιαδήποτε στήλη",
	
	"trueLabel": "Αληθές",
	"falseLabel": "Ψευδές"
})
//end v1.x content
);

},
'dojo/cldr/nls/el/gregorian':function(){
define(
"dojo/cldr/nls/el/gregorian", //begin v1.x content
{
	"months-format-narrow": [
		"Ι",
		"Φ",
		"Μ",
		"Α",
		"Μ",
		"Ι",
		"Ι",
		"Α",
		"Σ",
		"Ο",
		"Ν",
		"Δ"
	],
	"field-weekday": "Ημέρα εβδομάδας",
	"dateFormatItem-yyQQQQ": "QQQQ yy",
	"dateFormatItem-yQQQ": "y QQQ",
	"dateFormatItem-yMEd": "EEE, d/M/yyyy",
	"dateFormatItem-MMMEd": "E, d MMM",
	"eraNarrow": [
		"π.Χ.",
		"μ.Χ."
	],
	"dateFormat-long": "d MMMM y",
	"months-format-wide": [
		"Ιανουαρίου",
		"Φεβρουαρίου",
		"Μαρτίου",
		"Απριλίου",
		"Μαΐου",
		"Ιουνίου",
		"Ιουλίου",
		"Αυγούστου",
		"Σεπτεμβρίου",
		"Οκτωβρίου",
		"Νοεμβρίου",
		"Δεκεμβρίου"
	],
	"dateFormatItem-EEEd": "EEE d",
	"dayPeriods-format-wide-pm": "μ.μ.",
	"dateFormat-full": "EEEE, d MMMM y",
	"dateFormatItem-Md": "d/M",
	"field-era": "Περίοδος",
	"dateFormatItem-yM": "M/yyyy",
	"months-standAlone-wide": [
		"Ιανουάριος",
		"Φεβρουάριος",
		"Μάρτιος",
		"Απρίλιος",
		"Μάιος",
		"Ιούνιος",
		"Ιούλιος",
		"Αύγουστος",
		"Σεπτέμβριος",
		"Οκτώβριος",
		"Νοέμβριος",
		"Δεκέμβριος"
	],
	"timeFormat-short": "h:mm a",
	"quarters-format-wide": [
		"1ο τρίμηνο",
		"2ο τρίμηνο",
		"3ο τρίμηνο",
		"4ο τρίμηνο"
	],
	"timeFormat-long": "h:mm:ss a z",
	"field-year": "Έτος",
	"dateFormatItem-yMMM": "LLL y",
	"dateFormatItem-yQ": "y Q",
	"dateFormatItem-yyyyMMMM": "LLLL y",
	"field-hour": "Ώρα",
	"dateFormatItem-MMdd": "dd/MM",
	"months-format-abbr": [
		"Ιαν",
		"Φεβ",
		"Μαρ",
		"Απρ",
		"Μαϊ",
		"Ιουν",
		"Ιουλ",
		"Αυγ",
		"Σεπ",
		"Οκτ",
		"Νοε",
		"Δεκ"
	],
	"dateFormatItem-yyQ": "Q yy",
	"timeFormat-full": "h:mm:ss a zzzz",
	"field-day-relative+0": "Σήμερα",
	"field-day-relative+1": "Αύριο",
	"field-day-relative+2": "Μεθαύριο",
	"dateFormatItem-H": "HH",
	"field-day-relative+3": "Σε τρεις ημέρες από τώρα",
	"months-standAlone-abbr": [
		"Ιαν",
		"Φεβ",
		"Μαρ",
		"Απρ",
		"Μαϊ",
		"Ιουν",
		"Ιουλ",
		"Αυγ",
		"Σεπ",
		"Οκτ",
		"Νοε",
		"Δεκ"
	],
	"quarters-format-abbr": [
		"Τ1",
		"Τ2",
		"Τ3",
		"Τ4"
	],
	"quarters-standAlone-wide": [
		"1ο τρίμηνο",
		"2ο τρίμηνο",
		"3ο τρίμηνο",
		"4ο τρίμηνο"
	],
	"dateFormatItem-HHmmss": "HH:mm:ss",
	"dateFormatItem-M": "L",
	"days-standAlone-wide": [
		"Κυριακή",
		"Δευτέρα",
		"Τρίτη",
		"Τετάρτη",
		"Πέμπτη",
		"Παρασκευή",
		"Σάββατο"
	],
	"dateFormatItem-MMMMd": "d MMMM",
	"dateFormatItem-yyMMM": "LLL yy",
	"timeFormat-medium": "h:mm:ss a",
	"dateFormatItem-Hm": "HH:mm",
	"quarters-standAlone-abbr": [
		"Τ1",
		"Τ2",
		"Τ3",
		"Τ4"
	],
	"eraAbbr": [
		"π.Χ.",
		"μ.Χ."
	],
	"field-minute": "Λεπτό",
	"field-dayperiod": "π.μ./μ.μ.",
	"days-standAlone-abbr": [
		"Κυρ",
		"Δευ",
		"Τρι",
		"Τετ",
		"Πεμ",
		"Παρ",
		"Σαβ"
	],
	"dateFormatItem-d": "d",
	"dateFormatItem-ms": "mm:ss",
	"field-day-relative+-1": "Χθες",
	"field-day-relative+-2": "Προχθές",
	"field-day-relative+-3": "Πριν από τρεις ημέρες",
	"dateFormatItem-MMMd": "d MMM",
	"dateFormatItem-MEd": "E, d/M",
	"field-day": "Ημέρα",
	"days-format-wide": [
		"Κυριακή",
		"Δευτέρα",
		"Τρίτη",
		"Τετάρτη",
		"Πέμπτη",
		"Παρασκευή",
		"Σάββατο"
	],
	"field-zone": "Ζώνη",
	"dateFormatItem-yyyyMM": "MM/yyyy",
	"dateFormatItem-y": "y",
	"months-standAlone-narrow": [
		"Ι",
		"Φ",
		"Μ",
		"Α",
		"Μ",
		"Ι",
		"Ι",
		"Α",
		"Σ",
		"Ο",
		"Ν",
		"Δ"
	],
	"dateFormatItem-yyMM": "MM/yy",
	"days-format-abbr": [
		"Κυρ",
		"Δευ",
		"Τρι",
		"Τετ",
		"Πεμ",
		"Παρ",
		"Σαβ"
	],
	"eraNames": [
		"π.Χ.",
		"μ.Χ."
	],
	"days-format-narrow": [
		"Κ",
		"Δ",
		"Τ",
		"Τ",
		"Π",
		"Π",
		"Σ"
	],
	"field-month": "Μήνας",
	"days-standAlone-narrow": [
		"Κ",
		"Δ",
		"Τ",
		"Τ",
		"Π",
		"Π",
		"Σ"
	],
	"dateFormatItem-MMM": "LLL",
	"dateFormatItem-HHmm": "HH:mm",
	"dayPeriods-format-wide-am": "π.μ.",
	"dateFormatItem-MMMMEd": "E, d MMMM",
	"dateFormatItem-MMMMdd": "dd MMMM",
	"dateFormat-short": "d/M/yy",
	"field-second": "Δευτερόλεπτο",
	"dateFormatItem-yMMMEd": "EEE, d MMM y",
	"dateFormatItem-Ed": "E d",
	"field-week": "Εβδομάδα",
	"dateFormat-medium": "d MMM y",
	"dateFormatItem-mmss": "mm:ss",
	"dateFormatItem-yyyy": "y"
}
//end v1.x content
);
},
'dojo/cldr/nls/el/number':function(){
define(
"dojo/cldr/nls/el/number", //begin v1.x content
{
	"group": ".",
	"percentSign": "%",
	"exponential": "e",
	"percentFormat": "#,##0%",
	"list": ",",
	"infinity": "∞",
	"patternDigit": "#",
	"minusSign": "-",
	"decimal": ",",
	"nan": "NaN",
	"nativeZeroDigit": "0",
	"perMille": "‰",
	"currencyFormat": "#,##0.00 ¤",
	"plusSign": "+"
}
//end v1.x content
);
},
'dojox/grid/enhanced/nls/el/EnhancedGrid':function(){
define(
"dojox/grid/enhanced/nls/el/EnhancedGrid", //begin v1.x content
({
	singleSort: "Απλή ταξινόμηση",
	nestedSort: "Ένθετη ταξινόμηση",
	ascending: "Αύξουσα",
	descending: "Φθίνουσα",
	sortingState: "${0} - ${1}",
	unsorted: "Χωρίς ταξινόμηση αυτής της στήλης",
	indirectSelectionRadio: "Γραμμή ${0}, μονή επιλογή, κουμπί επιλογής",
	indirectSelectionCheckBox: "Γραμμή ${0}, πολλαπλές επιλογές, τετραγωνίδιο επιλογής",
	selectAll: "Επιλογή όλων"
})
//end v1.x content
);


},
'dijit/_editor/nls/el/commands':function(){
define(
"dijit/_editor/nls/el/commands", //begin v1.x content
({
	'bold': 'Έντονα',
	'copy': 'Αντιγραφή',
	'cut': 'Αποκοπή',
	'delete': 'Διαγραφή',
	'indent': 'Εσοχή',
	'insertHorizontalRule': 'Οριζόντια γραμμή',
	'insertOrderedList': 'Αριθμημένη λίστα',
	'insertUnorderedList': 'Λίστα με κουκίδες',
	'italic': 'Πλάγια',
	'justifyCenter': 'Στοίχιση στο κέντρο',
	'justifyFull': 'Πλήρης στοίχιση',
	'justifyLeft': 'Στοίχιση αριστερά',
	'justifyRight': 'Στοίχιση δεξιά',
	'outdent': 'Μείωση περιθωρίου',
	'paste': 'Επικόλληση',
	'redo': 'Ακύρωση αναίρεσης',
	'removeFormat': 'Αφαίρεση μορφοποίησης',
	'selectAll': 'Επιλογή όλων',
	'strikethrough': 'Διαγράμμιση',
	'subscript': 'Δείκτης',
	'superscript': 'Εκθέτης',
	'underline': 'Υπογράμμιση',
	'undo': 'Αναίρεση',
	'unlink': 'Αφαίρεση σύνδεσης',
	'createLink': 'Δημιουργία σύνδεσης',
	'toggleDir': 'Εναλλαγή κατεύθυνσης',
	'insertImage': 'Εισαγωγή εικόνας',
	'insertTable': 'Εισαγωγή/Τροποποίηση πίνακα',
	'toggleTableBorder': 'Εναλλαγή εμφάνισης περιγράμματος πίνακα',
	'deleteTable': 'Διαγραφή πίνακα',
	'tableProp': 'Ιδιότητα πίνακα',
	'htmlToggle': 'Πρωτογενής κώδικας HTML',
	'foreColor': 'Χρώμα προσκηνίου',
	'hiliteColor': 'Χρώμα φόντου',
	'plainFormatBlock': 'Στυλ παραγράφου',
	'formatBlock': 'Στυλ παραγράφου',
	'fontSize': 'Μέγεθος γραμματοσειράς',
	'fontName': 'Όνομα γραμματοσειράς',
	'tabIndent': 'Εσοχή με το πλήκτρο Tab',
	"fullScreen": "Εναλλαγή κατάστασης πλήρους οθόνης",
	"viewSource": "Προβολή προέλευσης HTML",
	"print": "Εκτύπωση",
	"newPage": "Νέα σελίδα",
	/* Error messages */
	'systemShortcut': 'Σε αυτό το πρόγραμμα πλοήγησης, η ενέργεια "${0}" είναι διαθέσιμη μόνο με τη χρήση μιας συντόμευσης πληκτρολογίου. Χρησιμοποιήστε τη συντόμευση ${1}.'
})

//end v1.x content
);

},
'dojox/grid/enhanced/nls/el/Pagination':function(){
define(
"dojox/grid/enhanced/nls/el/Pagination", //begin v1.x content
({
	"descTemplate": "${2} - ${3} από ${1} ${0}",
	"firstTip": "Πρώτη σελίδα",
	"lastTip": "Τελευταία σελίδα",
	"nextTip": "Επόμενη σελίδα",
	"prevTip": "Προηγούμενη σελίδα",
	"itemTitle": "στοιχεία",
	"singularItemTitle": "στοιχείο",
	"pageStepLabelTemplate": "Σελίδα ${0}",
	"pageSizeLabelTemplate": "${0} στοιχεία ανά σελίδα",
	"allItemsLabelTemplate": "Όλα τα στοιχεία",
	"gotoButtonTitle": "Μετάβαση σε συγκεκριμένη σελίδα",
	"dialogTitle": "Μετάβαση σε σελίδα",
	"dialogIndication": "Καθορίστε τον αριθμό της σελίδας",
	"pageCountIndication": " (${0} σελίδες)",
	"dialogConfirm": "Μετάβαση",
	"dialogCancel": "Ακύρωση",
	"all": "όλα"
})
//end v1.x content
);

},
'dijit/form/nls/el/validate':function(){
define(
"dijit/form/nls/el/validate", //begin v1.x content
({
	invalidMessage: "Η τιμή που καταχωρήσατε δεν είναι έγκυρη.",
	missingMessage: "Η τιμή αυτή πρέπει απαραίτητα να καθοριστεί.",
	rangeMessage: "Η τιμή αυτή δεν ανήκει στο εύρος έγκυρων τιμών."
})
//end v1.x content
);

},
'dojo/cldr/nls/el/currency':function(){
define(
"dojo/cldr/nls/el/currency", //begin v1.x content
{
	"HKD_displayName": "Δολάριο Χονγκ Κονγκ",
	"CHF_displayName": "Φράγκο Ελβετίας",
	"CAD_displayName": "Δολάριο Καναδά",
	"CNY_displayName": "Γιουάν Ρενμίμπι Κίνας",
	"AUD_displayName": "Δολάριο Αυστραλίας",
	"JPY_displayName": "Γιεν Ιαπωνίας",
	"USD_displayName": "Δολάριο ΗΠΑ",
	"GBP_displayName": "Λίρα Στερλίνα Βρετανίας",
	"EUR_displayName": "Ευρώ"
}
//end v1.x content
);
},
'dijit/form/nls/el/ComboBox':function(){
define(
"dijit/form/nls/el/ComboBox", //begin v1.x content
({
		previousMessage: "Προηγούμενες επιλογές",
		nextMessage: "Περισσότερες επιλογές"
})
//end v1.x content
);

},
'dijit/nls/el/loading':function(){
define(
"dijit/nls/el/loading", //begin v1.x content
({
	loadingState: "Φόρτωση...",
	errorState: "Σας ζητούμε συγνώμη, παρουσιάστηκε σφάλμα"
})
//end v1.x content
);

}}});
define("dojo/nls/freenasdojo_el", [], 1);
