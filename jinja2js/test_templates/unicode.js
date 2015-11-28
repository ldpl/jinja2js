(function(__ns, _) {
__ns.unicode_in_macro = function() {
    var __data = _.parse_args(arguments, []);
    var __output = '';
    __output += 'тест';
    return __output;
};

__ns.unicode_in_dict_keys = function() {
    var __data = _.parse_args(arguments, []);
    var __output = '';
    __output += '\n    ';
    var d = {'тест': 'aaa'};
    __output += '\n';
    return __output;
};

__ns.unicode_in_dict_values = function() {
    var __data = _.parse_args(arguments, []);
    var __output = '';
    __output += '\n    ';
    var d = {'aa': 'тест'};
    __output += '\n';
    return __output;
};
})(window.jinja2js = window.jinja2js || {}, jinja2support);
