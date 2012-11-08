import difflib
import fnmatch
import os
import re
import json

from nose.tools import raises
import spidermonkey

from jinja2 import Environment, PackageLoader, Template
from jinja2.compiler import TemplateAssertionError

import jscompiler


env = Environment(loader=PackageLoader('jinja2js', 'test_templates'),
                  autoescape=True)


def compare(result, expected):
    # Vim adds an extra linefeed at the end of the file, so we get rid of it
    result = result.strip()
    expected = expected.strip()
    if result != expected:
        for change in difflib.unified_diff(result.strip().split('\n'),
                                           expected.strip().split('\n')):
            print change
        assert False, "Result and expected do not match"


def execute_template(js_source, source_file, support_file, tests_file):
    j2_template = env.get_template(source_file)
    tests = []
    for l in open(tests_file):
        l = l.strip()
        if not l or l[0] == '#':
            continue
        lang = 'any'
        if l.startswith('js>'):
            l = l[3:].strip()
            lang = 'js'
        elif l.startswith('py>'):
            l = l[3:].strip()
            lang = 'py'

        args_start_pos = l.find('(')
        args_end_pos = l.rfind(')')
        macro_name = l[:args_start_pos]
        args_str = l[args_start_pos: args_end_pos + 1]
        args_json = '[' + args_str[1:-1] + ']'
        if lang == 'any':
            args = json.loads(args_json)
            tests.append([macro_name, args, args_str])
        elif lang == 'js':
            if tests and tests[-1][0] == macro_name:
                tests[-1][2] = args_str
            else:
                tests.append([macro_name, None, args_str])
        elif lang == 'py':
            args = eval(args_json)
            if tests and tests[-1][0] == macro_name:
                tests[-1][1] = args
            else:
                tests.append([macro_name, args, None])

    rt = spidermonkey.Runtime()
    cx = rt.new_context()
    window = {}
    cx.add_global('window', window)
    support_js = open(support_file).read()
    cx.execute(support_js)
    cx.add_global('jinja2support', window['jinja2support'])
    cx.execute(js_source)
    for macro, args_py, args_js in tests:
        expected = getattr(j2_template.module, macro)(*args_py)
        js_command = 'window.jinja2js.' + macro + args_js
        result = cx.execute(js_command).strip()
        if result != expected:
            print "Test:", macro, args_str
            print "Expected:"
            print expected
            print "Result:"
            print result
            assert False, "Test failed"


def load_compare_execute(directory, support_file, source_file):
    js_file = os.path.join(directory, re.sub('\\.jinja$', '.js', source_file))
    tpl_src = jscompiler.generate(env, js_file, source_file)
    correct_test = False
    if os.path.exists(js_file):
        correct_test = True
        expected = open(js_file).read()
        compare(tpl_src, expected)
    test_file = os.path.join(directory, re.sub('\\.jinja$', '.test', source_file))
    if os.path.exists(test_file):
        correct_test = True
        execute_template(tpl_src, source_file, support_file, test_file)
    if not correct_test:
        assert False, "Invalid test: .js or .test file required"


def test_file_templates():
    # test will run from either location
    directory = 'jinja2js/test_templates'
    if os.path.isfile('tests.py'):
        directory = 'test_templates'
    support_file = os.path.join(directory, os.pardir, os.pardir,
                                'js', 'jinja2support.js')

    files = os.listdir(directory)
    files = fnmatch.filter(files, '*.jinja')

    for f in files:
        yield load_compare_execute, directory, support_file, f


@raises(TemplateAssertionError)
def test_undeclared_var():
    # variable is undeclared
    src = """{% macro hello() %}{{ name }}{% endmacro %}"""
    node = env._parse(src, None, None)
    jscompiler._generate(node, env, "var1.html", "var1.html", 'jinja2js')
