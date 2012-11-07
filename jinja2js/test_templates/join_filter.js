(function(__ns, _) {
__ns.join_filter_default = function() {
    var __data = _.parse_args(arguments, []);
    var __output = '';
    __output += _.escape(['a', 'b', 'c'].join(''));
    return __output;
};

__ns.join_filter_comma = function() {
    var __data = _.parse_args(arguments, []);
    var __output = '';
    __output += _.escape(['a', 'b', 'c'].join(','));
    return __output;
};

__ns.join_filter_var_arg = function() {
    var __data = _.parse_args(arguments, ['separator']);
    var __output = '';
    __output += _.escape(['a', 'b', 'c'].join(__data.separator));
    return __output;
};

__ns.join_filter_array_arg = function() {
    var __data = _.parse_args(arguments, ['separators', 'index']);
    var __output = '';
    __output += _.escape(['a', 'b', 'c'].join(__data.separators[__data.index]));
    return __output;
};

__ns.join_filter_complex_arg = function() {
    var __data = _.parse_args(arguments, ['config', 'type']);
    var __output = '';
    __output += _.escape(['a', 'b', 'c'].join(__data.config.separator[__data.type].value));
    return __output;
};

__ns.join_filter = function() {
    var __data = _.parse_args(arguments, ['value', 'separator']);
    var __output = '';
    __output += _.escape(__data.value.join(__data.separator));
    return __output;
};
})(window.jinja2js = window.jinja2js || {}, jinja2support);
