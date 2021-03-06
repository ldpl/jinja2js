import difflib
import fnmatch
import os
import re
import json

from nose.tools import raises
import spidermonkey  # pip install -e "git+https://github.com/andrewleech/python-spidermonkey-1#egg=python-spidermonkey"
from jinja2 import Environment, PackageLoader
from jinja2.compiler import TemplateAssertionError

from . import jscompiler


loader = PackageLoader('jinja2js', 'test_templates')
env = Environment(loader=loader, autoescape=True)
ENVIRONMENTS = {
    'default': env,
    'noescape': Environment(loader=loader, autoescape=False)
}


def compare(result, expected):
    # Vim adds an extra linefeed at the end of the file, so we get rid of it
    result = result.strip()
    expected = expected.strip()
    if result != expected:
        for change in difflib.unified_diff(expected.strip().split('\n'),
                                           result.strip().split('\n')):
            print(change)
        assert False, "Result and expected do not match"


def execute_template(source_file, support_files, tests_file):
    tests = []
    used_envs = set()
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

        env_names = ['default', 'noescape']
        for en in ENVIRONMENTS.keys():
            if not l.startswith(en + '>'):
                continue
            env_names = [en]
            l = l[len(en) + 1:].strip()
            break
        used_envs.update(env_names)

        args_start_pos = l.find('(')
        args_end_pos = l.rfind(')')
        macro_name = l[:args_start_pos]
        args_str = l[args_start_pos: args_end_pos + 1]
        args_json = '[' + args_str[1:-1] + ']'
        if lang == 'any':
            args = json.loads(args_json)
            tests.append([macro_name, args, args_str, env_names])
        elif lang == 'js':
            if tests and tests[-1][0] == macro_name:
                tests[-1][2] = args_str
            else:
                tests.append([macro_name, None, args_str, env_names])
        elif lang == 'py':
            args = eval(args_json)
            if tests and tests[-1][0] == macro_name:
                tests[-1][1] = args
            else:
                tests.append([macro_name, args, None, env_names])

    sm_runtime = spidermonkey.Runtime()

    j2_templates = {}
    js_contexts = {}
    js_sources = {}
    for env_name in used_envs:
        env = ENVIRONMENTS[env_name]
        j2_templates[env_name] = env.get_template(source_file)
        js_source = jscompiler.generate(env, None, source_file)
        print(js_source)
        cx = sm_runtime.new_context()
        window = {}
        cx.add_global('window', window)
        for sf in support_files:
            support_js = open(sf).read()
            cx.execute(support_js)
        cx.add_global('jinja2support', window['jinja2support'])
        cx.execute(js_source)
        js_contexts[env_name] = cx
        js_sources[env_name] = js_source

    for macro, args_py, args_js, env_names in tests:
        for e in env_names:
            expected = getattr(j2_templates[e].module, macro)(*args_py)
            js_command = 'window.jinja2js.' + macro + args_js
            result = js_contexts[e].execute(js_command).strip()
            if result != expected:
                print(js_sources[e])
                print("Test:", e, macro, args_str)
                print("Expected:")
                print(expected)
                print("Result:")
                print(result)
                assert False, "Test failed"


def load_compare(directory, support_files, source_file, js_file):
    expected = open(js_file).read()
    tpl_src = jscompiler.generate(env, js_file, source_file)
    compare(tpl_src, expected)

def load_execute(directory, support_files, source_file, test_file):
    execute_template(source_file, support_files, test_file)

def test_file_templates():
    # test will run from either location
    directory = 'jinja2js/test_templates'
    if os.path.isfile('tests.py'):
        directory = 'test_templates'
    support_file = os.path.join(directory, os.pardir, os.pardir,
                                'js', 'jinja2support.js')
    sprintf_file = os.path.join(directory, os.pardir, os.pardir,
                                'js', 'sprintf-0.7-beta1.js')

    files = os.listdir(directory)
    files = fnmatch.filter(files, '*.jinja')

    for f in files:
        # if f != 'for_loop_condition.jinja': continue
        test_file = os.path.join(directory, re.sub('\\.jinja$', '.test', f))
        js_file = os.path.join(directory, re.sub('\\.jinja$', '.js', f))
        if os.path.exists(test_file):
            yield load_execute, directory, (support_file, sprintf_file), f, test_file
        elif os.path.exists(js_file):
            yield load_compare, directory, (support_file, sprintf_file), f, js_file
        else:
            assert False, f".js or .test file required for {f}"


@raises(TemplateAssertionError)
def test_undeclared_var():
    # variable is undeclared
    src = """{% macro hello() %}{{ name }}{% endmacro %}"""
    node = env._parse(src, None, None)
    jscompiler._generate(node, env, "var1.html", "var1.html", 'jinja2js')
