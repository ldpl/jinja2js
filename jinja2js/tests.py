import difflib
import fnmatch
import os
import re

from nose.tools import raises
import spidermonkey

from jinja2 import Environment, PackageLoader
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


def load_and_compare(source_file, expected_file):
    src = jscompiler.generate(env, expected_file, source_file)
    with open(expected_file) as f:
        expected = f.read()
        compare(src, expected)


def execute_js(source_file, tests_file):
    tests = []
    for l in open(tests_file):
        l = l.strip()
        if l.startswith('>'):
            content = l[1:].strip()
            tests.append([content, None])
        elif l.startswith('<'):
            content = l[1:].strip()
            if tests[-1][1] is None:
                tests[-1][1] = content
            else:
                tests[-1][1] += '\n' + content
    rt = spidermonkey.Runtime()
    cx = rt.new_context()
    window = {}
    cx.add_global('window', window)
    support_js = open('../js/jinja2support.js').read()
    cx.execute(support_js)
    cx.add_global('jinja2support', window['jinja2support'])
    src = jscompiler.generate(env, None, source_file)
    cx.execute(src)
    for command, expected in tests:
        result = cx.execute('window.jinja2js.' + command).strip()
        if result != expected:
            print "Test:", command
            print "Expected:"
            print expected
            print "Result:"
            print result
            assert False, "Test failed"


def test_file_templates():
    # test will run from either location
    directory = 'jinja2js/test_templates'
    if os.path.isfile('tests.py'):
        directory = 'test_templates'

    files = os.listdir(directory)
    files = fnmatch.filter(files, '*.jinja')

    for f in files:
        js_file = os.path.join(directory, re.sub('\\.jinja$', '.js', f))
        correct_test = False
        if os.path.exists(js_file):
            correct_test = True
            yield load_and_compare, f, js_file
        test_file = os.path.join(directory, re.sub('\\.jinja$', '.test', f))
        if os.path.exists(test_file):
            correct_test = True
            yield execute_js, f, test_file
        if not correct_test:
            def fail():
                assert False, "Invalid test: .js or .test file required"
            yield fail


@raises(TemplateAssertionError)
def test_undeclared_var():
    # variable is undeclared
    src = """{% macro hello() %}{{ name }}{% endmacro %}"""
    node = env._parse(src, None, None)
    jscompiler._generate(node, env, "var1.html", "var1.html", 'jinja2js')
