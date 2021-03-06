(function(jinja2support) {
    var toString = Object.prototype.toString;
    var has = Object.prototype.hasOwnProperty;
    var indexOf = Array.prototype.indexOf;
    var objectKeys;
    if (!Object.keys) {
        objectKeys = function (obj) {
            res = [];
            for (var k in obj)
                if (has.call(obj, k))
                    res.push(k);
            return res;
        };
    } else {
        objectKeys = Object.keys;
    }

    var _str_to_type = {};
    var _types = "Boolean Number String Function Array Date RegExp".split(" ");
    for (var i = 0; i < _types.length; i++) {
        var obj_str = "[object " + _types[i] + "]";
        _str_to_type[obj_str] = _types[i].toLowerCase();
    }
    var type_of = function (value) {
        if (value === undefined) return 'undefined';
        if (value === null) return 'null';
        type_str = toString.call(value);
        if (type_str in _str_to_type)
            return _str_to_type[type_str];
        return 'object';
    };


    jinja2support.parse_args = function(args, argspec) {
        var data = {};
        if (typeof(args[args.length - 1]) === 'function') {
            data.__caller = args[args.length - 1];
        }
        for (var i = 0; i < argspec.length; i++) {
            data[argspec[i]] = args[i];
        }
        return data;
    };

    jinja2support.escape = function(str) {
        return ('' + str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#x27;')
            .replace(/\//g, '&#x2F;');
    };

    jinja2support.in_ = function(value, collection) {
        if (type_of(collection) === 'array') {
            if (indexOf) {
                return indexOf.call(collection, value) > -1;
            }
            for (var i = 0, l = collection.length; i < l; i++) {
                if (collection[i] === value) {
                    return true;
                }
            }
        }
        return value in collection;
    };

    jinja2support.not = function(value) {
        return !jinja2support.truth(value);
    };

    jinja2support.truth = function(value) {
        var type = type_of(value);
        if (type === 'array') return value.length;
        if (type === 'object') {
            for (var prop in value)
                if (has.call(value, prop))
                    return true;
            return false;
        }
        return value;
    };

    jinja2support.arg_getter = function(index) {
        return function () {
            return arguments[index % arguments.length];
        };
    };

    jinja2support.iter = function(obj) {
        var otype = type_of(obj);
        if (otype == 'object') {
            return objectKeys(obj);
        }
        return obj;
    };

    jinja2support.length = function(value) {
        if (type_of(value) !== 'object')
            return value.length;
        var res = 0;
        for (var k in value)
            if (has.call(value, k))
                res++;
        return res;
    };

    jinja2support.truncate = function(str, length, killwords, end) {
        if (str.length <= length) {
            return str;
        }
        if (killwords) {
            return str.substring(0, length) + end;
        }
        var words = str.split(' ');
        var result = [];
        var m = 0;
        for (var i = 0; i < words.length; i++) {
            m += words[i].length + 1;
            if (m > length) break;
            result.push(words[i]);
        }
        result.push(end);
        return result.join(' ');
    };

    jinja2support.range = function(start, stop, step) {
        if (step === undefined) {
            step = 1;
        }
        if (stop === undefined) {
            stop = start;
            start = 0;
        }
        var res = [];
        // FIXME it's better to throw exception in case of step==0
        if (step === 0) return res;
        if (step > 0) {
            for(; start < stop; start += step) {
                res.push(start);
            }
        } else {
            for(; start > stop; start += step) {
                res.push(start);
            }
        }
        return res;
    };

    jinja2support.date_format = function(timestamp, format) {
        if (timestamp === null)
            return '';
        var date = new Date(timestamp * 1000);
        zero_padded = function (val) {
            if (val >= 10)
                return '' + val;
            return '0' + val;
        };
        MONTH_3 = {
            1: 'янв', 2: 'фев', 3: 'мар', 4: 'апр',
            5: 'май', 6: 'июн', 7: 'июл', 8: 'авг',
            9: 'сен', 10: 'окт', 11: 'ноя', 12: 'дек'
        };
        return ('' + format)
            .replace('H', date.getHours())
            .replace('i', zero_padded(date.getMinutes()))
            .replace('s', zero_padded(date.getSeconds()))
            .replace('d', zero_padded(date.getDate()))
            .replace('m', zero_padded(date.getMonth() + 1))
            .replace('M', MONTH_3[date.getMonth() + 1])
            .replace('Y', date.getFullYear());
    };

})(window.jinja2support = window.jinja2support || {});
