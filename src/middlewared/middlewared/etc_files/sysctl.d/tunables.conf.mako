<%
    tunables = middleware.call_sync2(middleware.services.tunable.query, [['type', '=', 'SYSCTL'], ['enabled', '=', True]])

    if not tunables:
        raise FileShouldNotExist()
%>\
% for tunable in tunables:
${tunable.var}=${tunable.value}
% endfor
