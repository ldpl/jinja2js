import unittest

from jinja2 import Environment, PackageLoader

import jinja2.compiler
import jinja2.nodes
import jinja2.optimizer
import jinja2.environment

import jscompiler


def generateMacro(node, environment, name, filename, autoescape=False):
    # Need to test when we are not using an Environment from jinja2js
    generator = jscompiler.MacroCodeGenerator(
        environment, jscompiler.Concat(), None, None)
    eval_ctx = jinja2.nodes.EvalContext(environment, name)
    eval_ctx.autoescape = autoescape
    generator.blockvisit(node.body, jscompiler.JSFrame(environment, eval_ctx))
    return generator.writer.stream.getvalue()


class JSConcatCompilerTemplateTestCase(unittest.TestCase):

    def get_compile_from_string(self, source, name=None, filename=None):
        node = self.env._parse(source, name, filename)
        # node = jinja2.optimizer.optimize(node, self.env)

        return node

    def setUp(self):
        super(JSConcatCompilerTemplateTestCase, self).setUp()
        self.env = Environment(loader=PackageLoader('pwt.jinja2js',
                                                    'test_templates'))

    def test_undeclared_var1(self):
        # variable is undeclared
        node = self.get_compile_from_string("""{% macro hello() %}
{{ name }}
{% endmacro %}
""")
        self.assertRaises(
            jinja2.compiler.TemplateAssertionError,
            generateMacro, node, self.env, "var1.html", "var1.html")

    def test_var1(self):
        node = self.get_compile_from_string("""{% macro hello(name) %}
{{ name }}
{% endmacro %}
""")
        source_code = generateMacro(node, self.env, "var1.html", "var1.html")

        self.assertEqual(source_code,
        """hello = function(opt_data, opt_sb, opt_caller) {
    var output = '';
    output += '\\n' + opt_data.name + '\\n';
    return output;
};""")

    def test_for13(self):
        # XXX - test for loop for conflicting variables. Here we have a
        # namespaced variable that gets required but conflicts with the
        # variable inside the loop that we created. If this is a problem
        # I will fix it, but it probable won't
        node = self.get_compile_from_string(
        """{% macro forinlist(jobs) -%}
{% for job in jobs %}{{ job.name }} does {{ jobData.name }}{% endfor %}
{%- endmacro %}""")

        source_code = jscompiler.generate(node, self.env, "f.html", "f.html")

        self.assertEqual(source_code,
        """forinlist = function(opt_data, opt_sb, opt_caller) {
    var output = '';
    var jobList = opt_data.jobs;
    var jobListLen = jobList.length;
    for (var jobIndex = 0; jobIndex < jobListLen; jobIndex++) {
        var jobData = jobList[jobIndex];
        output += jobData.name + ' does ' + jobData.name;
    }
    return output;
};""")

    def test_call_macro1(self):
        # call macro in same template, without arguments.
        node = self.get_compile_from_string("""{% macro testif(option) -%}
{% if option %}{{ option }}{% endif %}{% endmacro %}

{% macro testcall() %}{{ testif() }}{% endmacro %}""")

        source_code = jscompiler.generate(node, self.env, "f.html", "f.html")

        self.assertEqual(source_code,
        """testif = function(opt_data, opt_sb, opt_caller) {
    var output = '';
    if (opt_data.option) {
        output += opt_data.option;
    }
    return output;
};

testcall = function(opt_data, opt_sb, opt_caller) {
    var output = '';
    output += testif({});
    return output;
};""")

    def test_call_macro3(self):  # Copied from above and modified
        # call macro passing in a argument
        node = self.get_compile_from_string("""{% macro testif(option) -%}
{% if option %}{{ option }}{% endif %}{% endmacro %}

{% macro testcall() %}{{ testif(option = true) }}{% endmacro %}""")

        source_code = jscompiler.generate(node, self.env, "f.html", "f.html")

        self.assertEqual(source_code,
        """testif = function(opt_data, opt_sb, opt_caller) {
    var output = '';
    if (opt_data.option) {
        output += opt_data.option;
    }
    return output;
};

testcall = function(opt_data, opt_sb, opt_caller) {
    var output = '';
    output += testif({option: true});
    return output;
};""")

    def test_callblock1(self):
        node = self.get_compile_from_string("""{% macro render_dialog(type) -%}
<div class="type">{{ caller() }}</div>
{%- endmacro %}

{% macro render(name) -%}
{% call render_dialog(type = 'box') -%}
Hello {{ name }}!
{%- endcall %}
{%- endmacro %}
""")

        source_code = jscompiler.generate(node, self.env, "cb.html", "cb.html")

        self.assertEqual(source_code,
        """render_dialog = function(opt_data, opt_sb, opt_caller) {
    var output = '';
    output += '<div class="type">' + opt_caller({}) + '</div>';
    return output;
};

render = function(opt_data, opt_sb, opt_caller) {
    var output = '';
    func_caller = function(func_data, func_sb, func_caller) {
        var output = '';
        output += 'Hello ' + opt_data.name + '!';
        return output;
    };
    output += render_dialog({type: 'box'}, null, func_caller);
    return output;
};""")

    def test_filter_capitalize(self):
        # different in concat and stringbuilder modes
        node = self.get_compile_from_string(
            """{% macro trunc(s) %}{{ s|capitalize }}{% endmacro %}""")

        source_code = generateMacro(node, self.env, "f.html", "f.html")

        self.assertEqual(source_code,
        """trunc = function(opt_data, opt_sb, opt_caller) {
    var output = '';
    output += opt_data.s.substring(0, 1).toUpperCase() + opt_data.s.substring(1);
    return output;
};""")
