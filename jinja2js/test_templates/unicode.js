(function(__ns, _) {
__ns.unicode_in_macro = function() {
    var __data = _.parse_args(arguments, []);
    var __output = '';
    __output += '\u0442\u0435\u0441\u0442';
    return __output;
};

__ns.unicode_in_dict_keys = function() {
    var __data = _.parse_args(arguments, []);
    var __output = '';
    __output += '\n    ';
    var d = {'\u0442\u0435\u0441\u0442': 'aaa'};
    __output += '\n';
    return __output;
};

__ns.unicode_in_dict_values = function() {
    var __data = _.parse_args(arguments, []);
    var __output = '';
    __output += '\n    ';
    var d = {'aa': '\u0442\u0435\u0441\u0442'};
    __output += '\n';
    return __output;
};
})(window.jinja2js = window.jinja2js || {}, jinja2support);
