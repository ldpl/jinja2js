(function(jinja2support) {
    var toString = Object.prototype.toString;
    var has = Object.prototype.hasOwnProperty;
    var indexOf = Array.prototype.indexOf;

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
        if (toString.call(collection) === '[object Array]') {
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
        var type = toString.call(value);
        if (type === '[object Array]') return !value.length;
        if (type === '[object Object]') {
            for (var prop in value) if (has.call(value, prop)) return false;
            return true;
        }
        return !value;
    };

    jinja2support.truth = function(value) {
        return !jinja2support.not(value);
    };

    jinja2support.arg_getter = function(index) {
        return function () {
            return arguments[index % arguments.length];
        };
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

})(window.jinja2support = window.jinja2support || {});
