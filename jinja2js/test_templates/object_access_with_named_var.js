
(function(__ns, _) {
__ns.test_named_access = function() {
    var __data = _.parse_args(arguments, ['types', 'allowed_types']);
    var __output = '';
    __output += '\n';
    var tList = __data.allowed_types;
    var tListLen = tList.length;
    for (var tIndex = 0; tIndex < tListLen; tIndex++) {
        var tData = tList[tIndex];
        __output += '\n' + _.escape(__data.types[tData]) + '\n';
    }
    __output += '\n';
    return __output;
};

__ns.test_named_access_sub_value = function() {
    var __data = _.parse_args(arguments, ['types', 'allowed_types']);
    var __output = '';
    __output += '\n';
    var tList = __data.allowed_types;
    var tListLen = tList.length;
    for (var tIndex = 0; tIndex < tListLen; tIndex++) {
        var tData = tList[tIndex];
        __output += '\n' + _.escape(__data.types[tData.name]) + '\n';
    }
    __output += '\n';
    return __output;
};

__ns.test_named_access_assigned_value = function() {
    var __data = _.parse_args(arguments, ['allowed_types']);
    var __output = '';
    __output += '\n';
    var types = {'h1': 'H1'};
    __output += '\n';
    var tList = __data.allowed_types;
    var tListLen = tList.length;
    for (var tIndex = 0; tIndex < tListLen; tIndex++) {
        var tData = tList[tIndex];
        __output += '\n' + _.escape(types[tData.name]) + '\n';
    }
    __output += '\n';
    return __output;
};
})(window.jinja2js = window.jinja2js || {}, jinja2support);
