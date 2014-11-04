${disclaimer()}
% for tunable in ${collection.query('tunables')}:
${tunable["key"]}="${tunable["value"]}"
% endfor