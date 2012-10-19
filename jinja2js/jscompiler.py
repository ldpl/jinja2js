import re

from cStringIO import StringIO

from jinja2.visitor import NodeVisitor
import jinja2.nodes
import jinja2.compiler
from jinja2.utils import escape


UNARYOP = {
    "not ": "!"
    }

OPERATORS = {
    "eq":    "==",
    "ne":    "!=",
    "gt":    ">",
    "gteq":  ">=",
    "lt":    "<",
    "lteq":  "<=",
    }

LIST_OPERATORS = ('in', 'notin')

BOOL_NODES = (jinja2.nodes.And, jinja2.nodes.Or, jinja2.nodes.Not,
              jinja2.nodes.Compare)

BOOL_BIN_NODES = (jinja2.nodes.And, jinja2.nodes.Or, jinja2.nodes.Compare)


class JSFrameIdentifierVisitor(jinja2.compiler.FrameIdentifierVisitor):

    def __init__(self, identifiers, environment, ctx):
        # Manually setup the identifiers as older version of Jinja2 required
        # a hard_scope argument. So to work with older version just set the
        # hard_scope argument manually here compensate. It is not used
        # within the JS compiler.
        self.identifiers = identifiers
        self.hard_scope = False

        self.environment = environment
        self.ctx = ctx

    def blockvisit(self, nodes):
        for node in nodes:
            self.visit(node)

    # def visit_Name

    def visit_If(self, node):
        self.visit(node.test)
        for body in node.body:
            self.visit(body)
        for else_ in node.else_:
            self.visit(else_)

    def visit_Macro(self, node):
        self.identifiers.declared_locally.add(
            ("%s" % (node.name)).encode("utf-8"))

    def visit_Import(self, node):
        # register import target as declare_locally
        super(JSFrameIdentifierVisitor, self).visit_Import(node)

    # def visit_FromImport(self, node):

    # def visit_Assign

    def visit_For(self, node):
        # declare the iteration variable
        self.visit(node.iter)
        # declare the target variable
        self.visit(node.target)
        # declare anything in the for loops body. that might need to be
        # managed, like caller functions.
        self.blockvisit(node.body)

    # def visit_Callblock

    # def visit_FilterBlock

    # def visit_Block


class JSFrame(jinja2.compiler.Frame):

    def __init__(self, environment, eval_ctx, parent=None):
        super(JSFrame, self).__init__(eval_ctx, parent)

        # map local variables to imported code
        self.identifiers.imports = {}

        self.environment = environment

        # mapping of visit_Name callback to reassign variable names for use
        # in 'for' loops
        self.reassigned_names = {}

        # name -> method mapping for handling special variables in the
        # for loop
        self.forloop_buffer = None

        # Track if we are escaping some output
        self.escaped = False

    def inspect(self, nodes):
        """Walk the node and check for identifiers.  If the scope is hard (eg:
        enforce on a python level) overrides from outer scopes are tracked
        differently.
        """
        visitor = JSFrameIdentifierVisitor(
            self.identifiers, self.environment, self.eval_ctx)
        for node in nodes:
            visitor.visit(node)

    def inner(self):
        frame = JSFrame(self.environment, self.eval_ctx, self)
        frame.identifiers.imports = self.identifiers.imports
        return frame


class BaseCodeGenerator(NodeVisitor):

    def __init__(self, environment, name, filename):
        super(BaseCodeGenerator, self).__init__()

        self.environment = environment
        self.name = name
        self.filename = filename

        self.stream = StringIO()

        # the current line number
        self.code_lineno = 1

        # the debug information
        self.debug_info = []
        self._write_debug_info = None

        # the number of new lines before the next write()
        self._new_lines = 0

        # the line number of the last written statement
        self._last_line = 0

        # true if nothing was written so far.
        self._first_write = True

        # the current indentation multiplier
        self._indentation = 0

        # the character(s) to display as a single indent
        self._indentation_text = getattr(environment, 'js_indentation', '    ')

    def indent(self):
        """Indent by one."""
        self._indentation += 1

    def outdent(self, step=1):
        """Outdent by step."""
        self._indentation -= step

    def write(self, x, node=None):
        """Write a string into the output stream."""
        self.mark(node)
        if self._new_lines:
            if not self._first_write:
                self.stream.write('\n' * self._new_lines)
                self.code_lineno += self._new_lines
                if self._write_debug_info is not None:
                    self.debug_info.append((self._write_debug_info,
                                            self.code_lineno))
                    self._write_debug_info = None
            self._first_write = False
            self.stream.write(self._indentation_text * self._indentation)
            self._new_lines = 0
        self.stream.write(x)

    def writeline(self, x, node=None, extra=0):
        """Combination of newline and write."""
        self.newline(node, extra)
        self.write(x)

    def write_string_const(self, x):
        xrepr = repr(x)
        if isinstance(xrepr, unicode):
            self.write(xrepr[1:])
        else:
            self.write(xrepr)

    def mark(self, node):
        # Mark the current output to correspond to the node.
        if node is not None and node.lineno != self._last_line:
            self._write_debug_info = node.lineno
            self._last_line = node.lineno

    def newline(self, node=None, extra=0):
        """Add one or more newlines before the next write."""
        self._new_lines = max(self._new_lines, 1 + extra)
        self.mark(node)

    def writeline_startoutput(self, node, frame):
        self.writeline("var __output = '';", node)

    def writeline_endoutput(self, node, frame):
        self.writeline("return __output;", node)

    def writeline_outputappend(self, node, frame):
        self.writeline("__output += ", node)

    def write_outputappend_add(self, node, frame):
        self.write(" + ")

    def write_outputappend_end(self, node, frame):
        self.write(";")

    def write_htmlescape(self, node, frame):
        self.write('_.escape(')

    def write_htmlescape_end(self, node, frame):
        self.write(')')

    def blockvisit(self, nodes, frame):
        """
        Visit a list of noes ad block in a frame. Some times we want to
        pass lists to the the visit method. Get around this here.
        """
        # if frame.buffer
        for node in nodes:
            self.visit(node, frame)


class CodeGenerator(BaseCodeGenerator):

    def __init__(self, environment, name, filename, namespace="jinja2js"):
        super(CodeGenerator, self).__init__(environment, name, filename)
        self.namespace = namespace

    def visit_Template(self, node):
        """
        Setup the template output.

        Includes imports, macro definitions, etc.
        """

        have_extends = node.find(jinja2.nodes.Extends) is not None
        if have_extends:
            raise ValueError("JSCompiler doesn't support extends")

        have_blocks = node.find(jinja2.nodes.Block) is not None
        if have_blocks:
            raise ValueError("JSCompiler doesn't support blocks")

        eval_ctx = jinja2.nodes.EvalContext(self.environment, self.name)
        eval_ctx.encoding = "utf-8"

        # process the root
        frame = JSFrame(self.environment, eval_ctx)
        frame.inspect(node.body)
        frame.toplevel = frame.rootlevel = True

        self.writeline("(function(__ns, _) {\n")
        self.blockvisit(node.body, frame)
        self.writeline("})(window.%s = window.%s || {}, jinja2support);" %
                       (self.namespace, self.namespace))

    def visit_Import(self, node, frame):
        self.mark(node)

    def visit_Macro(self, node, frame):
        generator = MacroCodeGenerator(self.environment, self.stream,
                                       self.namespace, self.name,
                                       self.filename)
        generator.visit(node, frame)

    def visit_TemplateData(self, node, frame):
        self.mark(node)
        self.write(node.data)


class MacroCodeGenerator(BaseCodeGenerator):
    # split out the macro code generator. This generate the guts of the
    # JavaScript we need to render the templates. Note that we do this
    # here seperate from the template generator above as we want to restrict
    # the Jinja2 template syntax for the JS implementation and we want to
    # format the generate code a bit like the templates. Gaps between
    # templates, comments should be displayed in the JS file. We need them for
    # any closure compiler hints we may want to put in.

    def __init__(self, environment, stream, namespace, name, filename):
        super(MacroCodeGenerator, self).__init__(environment, name, filename)

        self.stream = stream
        self.namespace = namespace

    def visit_Output(self, node, frame):
        # JS is only interested in macros etc, as all of JavaScript
        # is rendered into the global namespace so we need to ignore data in
        # the templates that is out side the macros.
        if frame.toplevel:
            return

        finalize = unicode

        # try to evaluate as many chunks as possible into a static
        # string at compile time.
        body = []
        for child in node.nodes:
            try:
                const = child.as_const(frame.eval_ctx)
            except jinja2.nodes.Impossible:
                body.append(child)
                continue

            # the frame can't be volatile here, becaus otherwise the
            # as_const() function would raise an Impossible exception
            # at that point.
            try:
                if frame.eval_ctx.autoescape:
                    if hasattr(const, '__html__'):
                        const = const.__html__()
                    else:
                        const = escape(const)
                const = finalize(const)
            except:
                # if something goes wrong here we evaluate the node
                # at runtime for easier debugging
                body.append(child)
                continue

            if body and isinstance(body[-1], list):
                body[-1].append(const)
            else:
                body.append([const])

        start = True
        for item in body:
            if isinstance(item, list):
                if start:
                    self.writeline_outputappend(node, frame)
                    start = False
                else:
                    self.write_outputappend_add(node, frame)
                if getattr(self.environment, "strip_html_whitespace", False):
                    item = [strip_html_whitespace(itemhtml)
                            for itemhtml in item]
                self.write(repr("".join(item))[1:])
            else:
                if start:
                    self.writeline_outputappend(item, frame)
                    start = False
                else:
                    self.write_outputappend_add(item, frame)

                # autoescape, safe, and escape
                if isinstance(item, jinja2.nodes.Filter):
                    if item.name == "safe":
                        self.visit(item.node, frame)
                        continue

                if isinstance(item, jinja2.nodes.Call):
                    self.visit(item, frame)

                elif frame.eval_ctx.autoescape:
                    self.write_htmlescape(node, frame)
                    escaped_frame = frame.soft()
                    escaped_frame.escaped = True

                    self.visit(item, escaped_frame)

                    self.write_htmlescape_end(node, frame)
                else:
                    self.visit(item, frame)

        if not start:
            self.write_outputappend_end(node, frame)

    def visit_Filter(self, node, frame):
        # safe attribute with autoesacape is handled in visit_Output
        if node.name == "escape":
            if node.kwargs:
                raise Exception("No kwargs")

            if not frame.escaped:
                self.write_htmlescape(node, frame)
                frame = frame.soft()
                frame.escaped = True
                self.visit(node.node, frame)
                self.write_htmlescape_end(node, frame)
            else:
                self.visit(node.node, frame)
        elif node.name in FILTERS:
            kwargs = {}
            for kwarg in node.kwargs:
                kwargs[kwarg.key] = kwarg.value

            FILTERS[node.name](self, node, frame, *node.args, **kwargs)
        else:
            raise jinja2.compiler.TemplateAssertionError(
                "Filter does not exist: '%s'" % node.name,
                node.lineno, self.name, self.filename)

    def visit_Const(self, node, frame, dotted_name=None):
        # XXX - need to know the JavaScript ins and out here.
        val = node.value
        if val is None:
            output = "null"
        elif val is True:
            output = "true"
        elif val is False:
            output = "false"
        else:
            output = repr(val)

        if dotted_name is None:
            self.write(output)
        else:
            dotted_name.append(output)

        return False

    def visit_List(self, node, frame):
        self.write("[")
        for idx, item in enumerate(node.items):
            if idx:
                self.write(", ")
            self.visit(item, frame)
        self.write("]")

    def visit_Dict(self, node, frame):
        self.write("{")
        for idx, item in enumerate(node.items):
            if idx:
                self.write(", ")

            # item.key should be a constant string. Otherwise how do you
            # get to output a dictionary with a variable key string?
            # So it is either a `Const` or `Name` node.
            if isinstance(item.key, jinja2.nodes.Const):
                self.write_string_const(item.key.value)
            elif isinstance(item.key, jinja2.nodes.Name):
                self.write(item.key.name)
            else:
                raise jinja2.compiler.TemplateAssertionError(
                    "Dictionary keys must be constant.",
                    item.key.lineno, self.name, self.filename)

            self.write(": ")
            self.visit(item.value, frame)

        self.write("}")

    def visit_Name(self, node, frame, dotted_name=None):
        # declared_parameter
        # declared
        # outer_undeclared
        # declared_locally
        # undeclared
        name = node.name
        isparam = False

        ids = frame.identifiers
        topframe = frame
        while not topframe.toplevel:
            topframe = topframe.parent

        parent_ids = frame.parent.identifiers if frame.parent else None

        if name in ids.declared_parameter or name in ids.outer_undeclared:
            output = "__data." + name
            isparam = True
        elif parent_ids and name in parent_ids.declared_parameter:
            output = '__data.' + name

        elif name in frame.reassigned_names:
            output = frame.reassigned_names[name]

            isparam = True

        elif name in topframe.identifiers.declared_locally:
            output = "__ns." + name
        elif name in name in frame.identifiers.declared_locally:
            output = name

        elif name in ids.imports:
            # This is an import.
            output = ids.imports[name]

            frame.assigned_names.add(ids.imports[name])
        else:
            if dotted_name is None:
                raise jinja2.compiler.TemplateAssertionError(
                    "Variable '%s' not defined" % name,
                    node.lineno, self.name, self.filename)

            output = name

        if dotted_name is None:
            self.write(output)
        else:
            dotted_name.append(output)

        return isparam

    def visit_Slice(self, node, frame, dotted_name=None):
        if node.step is not None:
            raise NotImplementedError("jinja2js does not currently support "
                                      "steps in slices")

        if node.start:
            self.visit(node.start, frame, dotted_name)
            start = dotted_name.pop()
        else:
            start = '0'

        if node.stop:
            self.visit(node.stop, frame, dotted_name)
            stop = ', %s' % dotted_name.pop()
        else:
            stop = ''

        dotted_name.append('slice(%s%s)' % (start, stop))

    def visit_Getitem(self, node, frame, dotted_name=None):

        write_variable = False
        if dotted_name is None:
            dotted_name = []
            write_variable = True

        self.visit(node.node, frame, dotted_name)

        arg_name = []
        self.visit(node.arg, frame, arg_name)

        if isinstance(node.arg, jinja2.nodes.Slice):
            dotted_name.extend(arg_name)
        else:
            node = dotted_name.pop()
            dotted_name.append("%s[%s]" % (node, '.'.join(arg_name)))

        if write_variable:
            self.write(".".join(dotted_name))

    def visit_Getattr(self, node, frame, dotted_name=None):
        # We only need to check when `loop` is the first name-space in the
        # Getattr node. Sometimes we have more then one level name-spaces and
        # we are inside a for loop, likely when we are calling other macros.
        if frame.forloop_buffer and getattr(node.node, "name", None) == "loop":
            if node.attr == "index0":
                self.write("%sIndex" % frame.forloop_buffer)
            elif node.attr == "index":
                self.write("%sIndex + 1" % frame.forloop_buffer)
            elif node.attr == "revindex0":
                self.write("%sListLen - %sIndex"
                                  % (frame.forloop_buffer,
                                     frame.forloop_buffer))
            elif node.attr == "revindex":
                self.write("%sListLen - %sIndex - 1"
                                  % (frame.forloop_buffer,
                                     frame.forloop_buffer))
            elif node.attr == "first":
                self.write("%sIndex == 0" % frame.forloop_buffer)
            elif node.attr == "last":
                self.write("%sIndex == (%sListLen - 1)"
                                  % (frame.forloop_buffer,
                                     frame.forloop_buffer))
            elif node.attr == "length":
                self.write("%sListLen" % frame.forloop_buffer)
            elif node.attr == "cycle":
                self.write('_.arg_getter(%sIndex)' % frame.forloop_buffer)
            else:
                raise AttributeError("loop.%s not defined" % node.attr)
        else:
            # write_variable is going to be true if dotted_name is None which
            # implies that we are gathering the variable name together. So
            # don't write it out yet.
            write_variable = False
            if dotted_name is None:
                dotted_name = []
                write_variable = True

            # collect variable name
            self.visit(node.node, frame, dotted_name)
            dotted_name.append(node.attr)

            if write_variable:
                self.write(".".join(dotted_name))

    def binop(operator):
        def visitor(self, node, frame):
            self.write("(")
            self.visit(node.left, frame)
            self.write(" %s " % operator)
            self.visit(node.right, frame)
            self.write(")")
        return visitor

    # Math operators
    visit_Add = binop("+")
    visit_Sub = binop("-")
    visit_Mul = binop("*")
    visit_Div = binop("/")
    visit_Mod = binop("%")

    def visit_FloorDiv(self, node, frame):
        self.write("Math.floor(")
        self.visit(node.left, frame)
        self.write(" / ")
        self.visit(node.right, frame)
        self.write(")")

    def visit_Pow(self, node, frame):
        self.write("Math.pow(")
        self.visit(node.left, frame)
        self.write(", ")
        self.visit(node.right, frame)
        self.write(")")

    def bool_binop(operator):

        def visitor(self, node, frame):
            left_bool = type(node.left) in BOOL_NODES
            left_bool_bin = type(node.left) in BOOL_BIN_NODES

            if left_bool_bin:
                self.write("(")

            if not left_bool:
                self.write("_.truth(")

            self.visit(node.left, frame)

            if not left_bool:
                self.write(")")

            if left_bool_bin:
                self.write(")")

            self.write(" %s " % operator)

            right_bool = type(node.right) in BOOL_NODES
            right_bool_bin = type(node.right) in BOOL_BIN_NODES

            if right_bool_bin:
                self.write("(")

            if not right_bool:
                self.write("_.truth(")

            self.visit(node.right, frame)

            if not right_bool:
                self.write(")")

            if right_bool_bin:
                self.write(")")

        return visitor

    visit_And = bool_binop('&&')
    visit_Or = bool_binop('||')

    def visit_Not(self, node, frame):
        start = "!(" if type(node.node) in BOOL_NODES else "_.not("
        self.write(start)
        self.visit(node.node, frame)
        self.write(")")

    def uaop(operator):
        def visitor(self, node, frame):
            self.write(UNARYOP.get(operator, operator) + "(")
            self.visit(node.node, frame)
            self.write(")")
        return visitor

    visit_Pos = uaop("+")
    visit_Neg = uaop("-")

    del binop, bool_binop, uaop

    def visit_Compare(self, node, frame):
        op = node.ops[0]
        if len(node.ops) == 1 and op.op in LIST_OPERATORS:
            if op.op == 'notin':
                self.write('!')
            self.write('_.in_(')
            self.visit(node.expr, frame)
            self.write(', ')
            self.visit(op.expr, frame)
            self.write(')')
        else:
            self.visit(node.expr, frame)
            # XXX - ops is a list. Can we have a list of comparisons
            for op in node.ops:
                self.visit(op, frame)

    def visit_Operand(self, node, frame):
        self.write(" %s " % OPERATORS[node.op])
        self.visit(node.expr, frame)

    def visit_If(self, node, frame):
        if_frame = frame.soft()

        test_bool = type(node.test) in BOOL_NODES

        start = "if (" if test_bool else "if (_.truth("
        end = ") {" if test_bool else ")) {"

        self.writeline(start, node)
        self.visit(node.test, if_frame)
        self.write(end)

        self.indent()
        self.blockvisit(node.body, if_frame)
        self.outdent()

        if node.else_:
            self.writeline("} else {")
            self.indent()
            self.blockvisit(node.else_, if_frame)
            self.outdent()

        self.writeline("}")

    def visit_For(self, node, frame):
        node.iter_child_nodes(exclude=("iter",))

        if node.recursive:
            raise NotImplementedError(
                "JSCompiler doesn't support recursive loops")

        # try to figure out if we have an extended loop.  An extended loop
        # is necessary if the loop is in recursive mode or if the special loop
        # variable is accessed in the body.
        extended_loop = "loop" in jinja2.compiler.find_undeclared(
            node.iter_child_nodes(only=("body",)), ("loop",))

        # JavaScript for loops don't change namespace
        loop_frame = frame.soft()

        if extended_loop:
            loop_frame.identifiers.add_special("loop")
            loop_frame.forloop_buffer = node.target.name
        for name in node.find_all(jinja2.nodes.Name):
            if name.ctx == "store" and name.name == "loop":
                raise jinja2.compiler.TemplateAssertionError(
                    "Can't assign to special loop variable in for-loop target",
                    name.lineno, self.name, self.filename)

        self.writeline("var %sList = " % node.target.name)
        self.visit(node.iter, loop_frame)
        self.write(";")

        self.writeline("var %(name)sListLen = %(name)sList.length;"
                       % {"name": node.target.name})
        if node.else_:
            self.writeline("if (%sListLen > 0) {" % node.target.name)
            self.indent()

        self.writeline("for (var %(name)sIndex = 0; %(name)sIndex <"
                       " %(name)sListLen; %(name)sIndex++) {"
                       % {"name": node.target.name})
        self.indent()

        self.writeline("var %(name)sData = %(name)sList[%(name)sIndex];"
                              % {"name": node.target.name})
        loop_frame.reassigned_names[node.target.name] =\
                "%sData" % node.target.name
        self.blockvisit(node.body, loop_frame)
        self.outdent()
        self.writeline("}")

        if node.else_:
            self.outdent()
            self.writeline("} else {")
            self.indent()
            self.blockvisit(node.else_, frame)
            self.outdent()
            self.writeline("}")

    def function_scoping(self, node, frame, children=None):
        if children is None:
            children = node.iter_child_nodes()

        func_frame = frame.inner()
        func_frame.inspect(children)

        # variables that are undeclared (accessed before declaration) and
        # declared locally *and* part of an outside scope raise a template
        # assertion error. Reason: we can't generate reasonable code from
        # it without aliasing all the variables.
        # this could be fixed in Python 3 where we have the nonlocal
        # keyword or if we switch to bytecode generation
        overriden_closure_vars = (
            func_frame.identifiers.undeclared &
            func_frame.identifiers.declared &
            (func_frame.identifiers.declared_locally |
             func_frame.identifiers.declared_parameter)
        )
        if overriden_closure_vars:
            raise jinja2.compiler.TemplateAssertionError(
                "It's not possible to set and access variables "
                "derived from an outer scope! (affects: %s)" % (
                    ", ".join(sorted(overriden_closure_vars)), node.lineno),
                    node.lineno, self.name, self.filename)

        # remove variables from a closure from the frame's undeclared
        # identifiers.
        func_frame.identifiers.undeclared -= (
            func_frame.identifiers.undeclared &
            func_frame.identifiers.declared
        )

        # Handle special variables.
        if "caller" in func_frame.identifiers.undeclared:
            func_frame.identifiers.undeclared.discard("caller")
            func_frame.reassigned_names["caller"] = "__data.__caller"

        return func_frame

    def macro_body(self, name, node, frame, children=None):
        frame = self.function_scoping(node, frame, children=children)

        self.writeline("__ns.%s = function() {" % name)
        self.indent()

        self.writeline("var __data = _.parse_args(arguments, [")
        js_args = ["'%s'" % arg.name for arg in node.args]
        self.write(", ".join(js_args))
        self.write("]);")
        self.writeline_startoutput(node, frame)
        self.blockvisit(node.body, frame)
        self.writeline_endoutput(node, frame)
        self.outdent()
        self.writeline("};")

    def caller_body(self, name, node, frame, children):
        """Caller is a local function and doesn't belong is the general NS"""
        self.writeline("%s = function() {" % name)
        self.indent()
        self.writeline_startoutput(node, frame)
        self.blockvisit(node.body, frame)
        self.writeline_endoutput(node, frame)
        self.outdent()
        self.writeline("};")

    def visit_Macro(self, node, frame):
        name = node.name
        self.macro_body(name, node, frame)
        frame.assigned_names.add("%s" % (name))

    def visit_CallBlock(self, node, frame):
        # node.call
        # node.body
        # Add the caller function to the macro.
        # XXX - Make sure we don't have a namespace cnoflict here.
        children = node.iter_child_nodes(exclude=("call",))
        self.caller_body("func_caller", node, frame, children=children)

        # call the macro passing in the caller method
        self.writeline_outputappend(node, frame)

        self.visit(node.call, frame, forward_caller="func_caller")
        self.write(";")

    def signature(self, node, frame, forward_caller):
        if node.args and node.kwargs:
            raise jinja2.compiler.TemplateAssertionError(
                "Function call with positional and keyword arguments "
                "are not allowed", node.lineno, self.name, self.filename)

        if node.dyn_args or node.dyn_kwargs:
            raise jinja2.compiler.TemplateAssertionError(
                "JS Does not support positional or keyword arguments",
                node.lineno, self.name, self.filename)

        if node.args:
            # We have only positional arguments here. In this case we assume
            # that we have an ordinary Java Script function we wish to call
            start_arg = True
            for arg in node.args:
                if not start_arg:
                    self.write(", ")
                self.visit(arg, frame)
                start_arg = False

            # Since this is a ordinary call bail out
            return

        # Now assume that we are calling an other macro
        # XXX - we should be able test this by looking up the environment to
        # see if that is the case.

        start_kw = True
        for kwarg in node.kwargs:
            if not start_kw:
                self.write(", ")
            self.visit(kwarg.value, frame)
            start_kw = False

        if forward_caller is not None:
            self.write(", null")

            self.write(", ")
            self.write(forward_caller)

    def visit_Call(self, node, frame, forward_caller=None):
        # function symbol to call
        dotted_name = []
        call_frame = frame.soft()
        call_frame.escaped = True
        self.visit(node.node, call_frame, dotted_name=dotted_name)
        func_name = ".".join(dotted_name)

        # Like signature(), this assumes that function calls with only
        # positional arguments are calls to javascript functions. This
        # allows you to call differently named functions in the client JS
        # than when rendering a template on the server.
        if node.args and not node.kwargs \
               and func_name in getattr(self.environment, "js_func_aliases",
                                        []):
            func_name = self.environment.js_func_aliases[func_name]

        # function signature
        self.write("%s(" % func_name)
        self.signature(node, frame, forward_caller)
        self.write(")")

    def visit_Assign(self, node, frame):
        # XXX - test that we don't override any variable names doing this
        self.newline(node)

        local_ids = frame.identifiers.declared_locally
        name = node.target.name

        if name in local_ids and name not in frame.assigned_names:
            frame.assigned_names.add(name)
            self.write("var ")

        self.visit(node.target, frame)
        self.write(" = ")
        self.visit(node.node, frame)
        self.write(";")

    def visit_CondExpr(self, node, frame):
        self.visit(node.test, frame)
        self.write(' ? ')
        self.visit(node.expr1, frame)
        self.write(' : ')
        # XXX - should this allow undefined else clauses? it's tough to
        #       really judge what the correct behaviour should be, but
        #       I have chosen an empty string since it is falsy and won't
        #       be printed if that's what the value is ultimately used for.
        if node.expr2:
            self.visit(node.expr2, frame)
        else:
            self.write("''")

_pre_tag_whitespace = re.compile(r'\s*<')
_post_tag_whitespace = re.compile(r'>\s*')
_excess_whitespace = re.compile(r'\s\s+')


def strip_html_whitespace(value):
    value = _pre_tag_whitespace.sub('<', value)
    value = _post_tag_whitespace.sub('>', value)
    return _excess_whitespace.sub(' ', value)

FILTERS = {}


class register_filter(object):

    def __init__(self, name):
        self.name = name

    def __call__(self, func):
        FILTERS[self.name] = func

        return func


@register_filter("string")
def filter_string(generator, node, frame):
    generator.write("'' + ")
    generator.visit(node.node, frame)


@register_filter("default")
def filter_default(generator, node, frame, default_value=""):
    generator.write("(")
    generator.visit(node.node, frame)
    generator.write(" ? ")
    generator.visit(node.node, frame)
    generator.write(" : ")
    generator.visit(default_value, frame)
    generator.write(")")


@register_filter("truncate")
def filter_truncate(generator, node, frame, length):
    generator.visit(node.node, frame)
    generator.write(".substring(0, ")
    generator.visit(length, frame)
    generator.write(")")


@register_filter("capitalize")
def filter_capitalize(generator, node, frame):
    generator.visit(node.node, frame)
    generator.write(".substring(0, 1).toUpperCase()")
    generator.write_outputappend_add(node, frame)
    generator.visit(node.node, frame)
    generator.write(".substring(1)")


@register_filter("last")
def filter_last(generator, node, frame):
    generator.visit(node.node, frame)
    generator.write(".pop()")


@register_filter("length")
def filter_length(generator, node, frame):
    generator.visit(node.node, frame)
    generator.write(".length")


@register_filter("replace")
def filter_replace(generator, node, frame, old, new):
    generator.visit(node.node, frame)
    generator.write(".replace(")
    generator.visit(old, frame)
    generator.write(", ")
    generator.visit(new, frame)
    generator.write(")")


@register_filter("round")
def filter_round(generator, node, frame, precision=jinja2.nodes.Const(0)):
    # get precision
    precision_value = []
    generator.visit(precision, frame, precision_value)
    precision = ".".join(precision_value)
    try:
        precision = 10 ** int(precision)
    except ValueError:
        # assume we are a parameter or declared variable and raise to power
        # of 10
        precision = "Math.pow(10, %s)" % precision

    generator.write("Math.round(")
    generator.visit(node.node, frame)
    if precision > 1:
        generator.write(" * %s" % precision)
    generator.write(")")
    if precision > 1:
        generator.write(" / %s" % precision)


@register_filter('join')
def filter_join(generator, node, frame, separator=None):
    generator.visit(node.node, frame)
    if separator is None:
        separator = "''"
    else:
        separator_value = []
        generator.visit(separator, frame, separator_value)
        separator = '.'.join(separator_value)
    generator.write('.join(%s)' % separator)


def generate(environment, name, filename, namespace="jinja2js"):
    """Generate the javascript source for jinja template."""
    src, path, uptodate = environment.loader.get_source(environment, filename)
    node = environment.parse(src)

    return _generate(node, environment, name, filename, namespace)


def generate_from_string(environment, src, namespace="jinja2js"):
    node = environment.parse(src)

    return _generate(node, environment, "", "", namespace)


def _generate(node, environment, name, filename, namespace):
    generator = CodeGenerator(environment, name, filename, namespace)
    generator.visit(node)
    return generator.stream.getvalue()
