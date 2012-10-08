from itertools import chain
import traceback
from pycparser.c_ast import FuncDef, ArrayDecl, Decl, While, Compound, Assignment, Constant, BinaryOp, If
from pycparser.c_parser import CParser
import sys
import re
from interp import BrainfuckInterpreter

__author__ = 'Michael Storm'


class Stack(object):
    def __init__(self):
        self.vars = {}

    def add(self, var, var_size):
        self.vars[var] = var_size

    def merge(self, other):
        self.vars = dict(chain(self.vars.items(), other.vars.items()))

    def names(self):
        return self.vars.keys()

    def size(self, var):
        return self.vars[var]

    def total_size(self):
        return sum(self.vars.values())

    def __str__(self):
        return self.vars.__str__()


class StackVisitor(object):
    def visitFuncDef(self, f):
        s = Stack()
        s.merge(self.visitFuncDecl(f.decl))
        s.merge(self.visitFuncBody(f.body))
        return s

    def visitFuncDecl(self, f):
        s = Stack()
        v = SizeVisitor()
        if f.type.args is not None:
            for param in f.type.args.params:
                s.add(param.name, v.visitDecl(param.type))
        return s

    def visitFuncBody(self, f):
        s = Stack()
        v = SizeVisitor()
        for item in f.block_items:
            if type(item) == Decl:
                s.add(item.name, v.visitDecl(item.type))
        return s


class SizeVisitor(object):
    def visitDecl(self, f):
        if type(f) == ArrayDecl:
            return self.visitArrayDecl(f)
        else:
            return self.visitTypeDecl(f)

    def visitArrayDecl(self, f):
        return f.dim * self.visitDecl(f.type)

    def visitTypeDecl(self, f):
        return self.visitIdentifierType(f.type)

    def visitIdentifierType(self, f):
        name = f.names[0]
        if name == 'char':
            return 1
        else:
            raise Exception("Unsupported type " + name)


class BytecodeVisitor(object):

    stackVisitor = StackVisitor()

    def __init__(self):
        self.unique_counter = 0

    def get_unique(self, base):
        unique = base + '_' + str(self.unique_counter)
        self.unique_counter += 1
        return unique

    def visit(self, f):
        if type(f) == Compound:
            return self.visitCompound(f)
        elif type(f) == If:
            return self.visitIf(f)
        elif type(f) == Assignment:
            return self.visitAssignment(f)
        elif type(f) == Decl:
            return self.visitDecl(f)
        elif type(f) == Constant:
            return self.visitConstant(f)
        elif type(f) == BinaryOp:
            return self.visitBinaryOp(f)
        else:
            print("Unknown type " + str(type(f)))
            f.show()
            print('#######')
            return []

    def visitAssignment(self, f):
        code = self.visit(f.rvalue)
        code.append(('pop', f.lvalue.name))
        return code

    def visitBinaryOp(self, f):
        code = []
        code.extend(self.visit(f.left))
        code.extend(self.visit(f.right))
        if f.op == '+':
            code.append(('addc',))
        elif f.op == '-':
            code.append(('subc',))
        else:
            raise Exception('Unsupported operator "' + f.op + '"')
        return code

    def parseCharConstant(self, c):
        if type(c) == int:
            return c
        # TODO need better check than this
        elif re.match(r"'.'", c) is not None:
            return ord(c[1])
        # TODO should check for overflow
        elif c.startswith(r"'\x"):
            return int(c[3:-1])
        else:
            raise Exception('Invalid constant "' + str(c) + '"')

    def visitCompound(self, f):
        code = []
        for item in f.block_items:
            code.extend(self.visit(item))
        return code

    def visitConstant(self, f):
        if f.type == 'char':
            return [('push', '{}c'.format(self.parseCharConstant(f.value)))]
        else:
            raise Exception('Unsupported constant type ' + f.type)

    def visitDecl(self, f):
        if f.init is not None:
            code = self.visit(f.init)
            code.append(('pop', f.name))
            return code
        else:
            return []

    def visitIf(self, f):
        true_block = self.visit(f.iftrue)
        true_label = self.get_unique('if')
        false_label = self.get_unique('if')
        done_label = self.get_unique('if_done')

        code = self.visit(f.cond)
        code.append(('cond', true_label, false_label))

        code.append(('label', true_label))
        code.extend(true_block)
        code.append(('jump', done_label))

        code.append(('label', false_label))
        if f.iffalse is not None:
            false_block = self.visit(f.iffalse)
            code.extend(false_block)

        code.append(('label', done_label))
        return code

    def visitMain(self, f):
        code = []
        stack = BytecodeVisitor.stackVisitor.visitFuncDef(f)
        print('stack: ' + str(stack))

        for name in stack.names():
            size = stack.size(name)
            code.append(('reserve', name, size))

        code.extend(self.visit(f.body))

        for name in stack.names():
            size = stack.size(name)
            code.append(('unreserve', name, size))

        return code

class BILVisitor(object):

    def __init__(self):
        self.stack = {}
        self.stack_depth = 0

    def visitProgram(self, program):
        label_nums = {}
        last_label_num = 1
        label_nums[program.main] = last_label_num
        for label, block in program.blocks:
            if label is not program.main:
                last_label_num += 1
                label_nums[label] = last_label_num

        code = [('[',)]

    def visit(self, c):
        if c[0] == 'reserve':
            return self.visitReserve(c)
        elif c[0] == 'unreserve':
            return self.visitUnreserve(c)
        elif c[0] == 'pop':
            return self.visitPop(c)
        elif c[0] == 'push':
            return self.visitPush(c)
        elif c[0] == 'addc':
            return self.visitAddC(c)
        elif c[0] == 'subc':
            return self.visitSubC(c)
        else:
            return [c]

    def visitReserve(self, c):
        self.stack[c[1]] = self.stack_depth
        self.stack_depth += c[2]
        return [('go', c[2])]

    def visitUnreserve(self, c):
        self.stack_depth -= c[2]
        del self.stack[c[1]]
        return [('go', c[2] * -1)]

    def visitPop(self, c):
        bc = [('left', 1), ('move', self.stack[c[1]] - self.stack_depth + 1, 0)]
        self.stack_depth -= 1
        return bc

    def visitPush(self, c):
        if c[1][0].isdigit() or c[1][0] == '-':
            if c[1][-1] == 'c':
                self.stack_depth += 1
                return [('plus', 0, int(c[1][0:-1])), ('go', 1)]
            else:
                raise Exception('Unsupported constant ' + c[1])
        else:
            raise Exception('Unsupported push operand ' + c[1])

    def visitAddC(self, c):
        self.stack_depth -= 1
        return [('move', -2, -1)]

    def visitSubC(self, c):
        self.stack_depth -= 1
        return [('unmove', -2, -1)]

    def visitBytecode(self, code):
        bil = []
        for c in code:
            bil.extend(self.visit(c))
        return bil


def addLabels(bytecode):
    label_num = 0

    def make_label():
        #nonlocal label_num
        lbl = 'lbl_' + str(label_num)
        label_num += 1
        return ('label', lbl)

    labeled_code = []
    for i in range(len(bytecode)):
        if bytecode[i][0] is not 'label':
            if i is 0 \
            or bytecode[i - 1][0] is 'cond' \
            or bytecode[i - 1][0] is 'jump':
                labeled_code.append(make_label())
        labeled_code.append(bytecode[i])
    return labeled_code


def addJumps(bytecode):
    jump_code = []
    for i in range(len(bytecode)):
        jump_code.append(bytecode[i])
        if i < len(bytecode)-1 and bytecode[i+1][0] is 'label':
            if bytecode[i][0] is not 'cond' and bytecode[i][0] is not 'jump':
                jump_code.append(('jump', bytecode[i+1][1]))
    return jump_code


class BasicBlock(object):
    def __init__(self):
        self.instrs = []
        self.true_exit = []
        self.false_exit = []

    def __repr__(self):
        return 'BasicBlock(instrs={}, true_exit=\'{}\', false_exit=\'{}\')'\
        .format(self.instrs, self.true_exit, self.false_exit)


class Program(object):
    def __init__(self, main, blocks):
        self.main = main
        self.blocks = blocks

    def __repr__(self):
        return 'Program(main=\'{}\', blocks={})'.format(self.main, self.blocks)


def getBasicBlocks(bytecode):
    blocks = {}
    current_block = None

    for bc in bytecode:
        if bc[0] == 'label':
            current_block = BasicBlock()
            blocks[bc[1]] = current_block
        elif bc[0] == 'jump':
            current_block.true_exit = bc[1]
        elif bc[0] == 'cond':
            current_block.true_exit = bc[1]
            current_block.false_exit = bc[2]
        current_block.instrs.append(bc)
    return blocks


def getProgram(bytecode):
    main = bytecode[0][1]
    blocks = getBasicBlocks(bytecode)
    return Program(main, blocks)

class BrainfuckSource(object):
    
    def __init__(self, bil, bf):
        self.bil = bil
        self.bf = bf

    def __repr__(self):
        return '{ bil=%s, src=%s }' % (self.bil, self.bf)

    def dump(self, indent):
        def print_indent(count):
            for i in range(0, count): print('    ', end='')

        print_indent(indent)
        indent += 1

        if len(self.bf) > 1 or (len(self.bf) > 0 and type(self.bf[0]) is not str):
            print('%s => ' % str(self.bil))

            for child in self.bf:
                if type(child) is str:
                    print_indent(indent)
                    print(child)
                else:
                    child.dump(indent)
        else:
            if type(self.bf[0]) is str:
                print('%s : %s' % (self.bf[0], str(self.bil)))

    def flattened(self):
        flat = ''
        for child in self.bf:
            if type(child) is str:
                flat += child
            else:
                flat += child.flattened()
        return flat

class SymbolicBF(object):

    def __init__(self):
        self.ops = []
        self.locs = []

    def add(self, children):
        self.ops.append(children[0])
        self.locs.extend(children[1])

class DefaultRepr(object):

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return str_impl(self, sorted(set(self.__dict__)))

class SymbolicLocation(DefaultRepr):

    def __init__(self, value=None, op=None):
        self.value = value
        self.op = op

    def apply_op(self):
        if self.op[0] == 'add':
            return self.value + op[1]
        elif self.op[0] == 'sub':
            return self.value - op[1]
        elif self.op[0] == 'mul':
            return self.value * op[1]

    def apply_value(self, value):
        if self.value is None:
            self.value = value
            return self.apply_op()
        else:
            return self.value.apply_value(value)

    def __add__(self, other):
        return SymbolicLocation(self, ('add', other))

    def __sub__(self, other):
        return SymbolicLocation(self, ('sub', other))

    def __mul__(self, other):
        return SymbolicLocation(self, ('mul', other))

    def __radd__(self, other):
        return SymbolicLocation(self, ('add', other))

    def __rsub__(self, other):
        return SymbolicLocation(self, ('sub', other * -1))

    def __rmul__(self, other):
        return SymbolicLocation(self, ('mul', other))

# from http://clarkupdike.blogspot.com/2009/01/canonical-python-str-method.html
def str_impl(anInstance, displayAttributeList):
    classLine = "%s(" % (anInstance.__class__.__name__)
    return (classLine + ", ".join(["%s: %s" % (key, anInstance.__dict__[key]) for key in displayAttributeList])) + ")"

class Op(DefaultRepr):

    def __init__(self):
        self.work_size = 0

    def get_work_size(self):
        return self.work_size

class Literal(Op):

    def __init__(self, bf):
        self.bf = bf

    def get_children(self):
        return []

class Go(Op):

    def __init__(self, dst):
        self.dst = dst

    def get_children(self):
        if type(self.dst) == SymbolicLocation:
            if self.dst.value is None:
                raise Exception('dst cannot be a SymbolicLocation with no value')
            else:
                dst = self.get_value()
        else:
            dst = self.dst

        if dst < 0:
            return [Literal('<' * (dst * -1))]
        else:
            return [Literal('>' * dst)]

class Copy(Op):

    def __init__(self, dst, src):
        self.dst = dst
        self.src = src

    def get_children(self, work):
        code = [Go(self.src)]
        code += [Literal('[-')]
        code += [Go(work[0] - self.src)]
        code += [Literal('+')]
        code += [Go(self.dst - work[0])]
        code += [Literal('+')]
        code += [Go(self.src - self.dst)]
        code += [Literal(']')]

        code += [Move(0, work[0] - self.src)]
        code += [Go(self.src * -1)]
        return code

class Cond(Op):

    def __init__(self, src, ops):
        self.src = src
        self.ops = ops

    def get_children(self, work):
        code = [Go(src)]
        code += [Literal('[')]
        code += ops
        code += [Zero(0)]
        code += [Literal(']')]
        code += [Go(self.src * -1)]
        return code

class MoveBase(Op):

    def __init__(self, src, dst):
        self.src = src
        self.dst = dst

    def get_children(self, work):
        code = [Go(src)]
        code += [Literal('[-')]
        code += [Go(self.dst - self.src)]
        code += [self.op]
        code += [Go(self.src - self.dst)]
        code += [']']
        code += [Go(self.src * -1)]
        return code

class Move(MoveBase):

    def __init__(self, src, dst):
        super().__init__(src, dst)
        self.op = '+'

class Unmove(MoveBase):

    def __init__(self, src, dst):
        super().__init__(src, dst)
        self.op = '-'

class IsZero(Op):

    def __init__(self, src, dst, negated=False):
        self.src = src
        self.dst = dst
        self.negated = negated

    def get_children(self, work):
        code = []
        if not self.negated:
            code += [Add(dst, 1)]

        code += [Cond(self.src, Add(self.dst - self.src, 1 if self.negated else -1))]
        return code

class And(Op):

    def __init__(self, dst, src_list):
        self.dst = dst
        self.src_list = src_list
        self.work_size = 1

    def get_children(self):
        if len(self.src_list) == 0:
            raise Exception('Opcode \'and\' must have at least one src cell')

        work = SymbolicLocation()
        code = [Add(work, len(self.src_list))]

        for src in self.src_list:
            code += [Cond(src, [Add(work - src, -1)])]

        code += [IsZero(self.dst, work)]
        return code

class Or(Op):

    def __init__(self, dst, src_list):
        self.dst = dst
        self.src_list = src_list

    def get_children(self, work):
        if len(self.src_list) == 0:
            raise Exception('Opcode \'or\' must have at least one src cell')

        code = []
        for src in self.src_list:
            code += [Cond(src, Add(self.dst - src, 1))]
        return code

class Xor(Op):

    def __init__(self, dst, src):
        self.dst = dst
        self.src = src

    def get_children(self, work):
        if len(self.src_list) < 2:
            raise Exception('Opcode \'xor\' must have at least two src cells')

        code = []
        for src in self.src_list:
            code += [Cond(src, Add(self.dst - src, 1))]

        code += [self.visit(('copy', work[0], self.dst, work[1]))]
        code += [self.visit(('iszero', work[0], work[1]))]
        #code += [self.visit((
        return code

class Add(Op):

    def __init__(self, dst, count):
        self.dst = dst
        self.count = count

    def get_children(self):
        return [Go(self.dst)] + [('-' if self.count < 0 else '+') * abs(self.count)] + [Go(self.dst * -1)]

def dump_ops(ops, depth=0):
    for op in ops:
        print(' ' * (depth*2), end='')
        if type(op) == str:
            print('"%s"' % op)
        else:
            print(op)
            children = op.get_children()
            dump_ops(children, depth+1)

class BrainfuckVisitor(object):

    def visit(self, c):
        if c[0] == 'go':
            result = self.visitGo(dst=c[1])
        elif c[0] == 'add':
            result = self.visitAdd(dst=c[1], count=c[2])
        elif c[0] == 'cond':
            result = self.visitCond(src=c[1], op=c[2])
        elif c[0] == 'move':
            result = self.visitMove(dst=c[1], src=c[2])
        elif c[0] == 'unmove':
            result = self.visitUnmove(c)
        elif c[0] == 'zero':
            result = self.visitZero(c[1])
        elif c[0] == 'copy':
            result = self.visitCopy(dst=c[1], src=c[2], work=c[3])
        elif c[0] == 'iszero':
            result = self.visitIsZero(c[1], c[2])
        elif c[0] == 'isnotzero':
            result = self.visitIsZero(c[1], c[2], negated=True)
        elif c[0] == 'iseq':
            result = self.visitIsEq(c)
        elif c[0] == 'and':
            result = self.visitAnd(c[1], c[2], c[3])
        else:
            raise Exception('Unrecognized BIL opcode ' + c[0])

        return BrainfuckSource(c, result)

    def visitGo(self, dst):
        if dst < 0:
            return ['<' * (dst * -1)]
        else:
            return ['>' * dst]

    def visitAnd(self, dst, src_list, work):
        if len(src_list) == 0:
            raise Exception('Opcode \'and\' must have at least one src cell')

        code = [self.visit(('add', work, len(src_list)))]

        for src in src_list:
            code += [self.visit(('cond', src, ('add', work - src, -1)))]

        code += [self.visit(('iszero', dst, work))]
        return code

    def visitOr(self, dst, src_list):
        if len(src_list) == 0:
            raise Exception('Opcode \'or\' must have at least one src cell')

        code = []
        for src in src_list:
            code += [self.visit(('cond', src, ('add', dst - src, 1)))]
        return code

    def visitXor(self, dst, src_list, work):
        if len(src_list) < 2:
            raise Exception('Opcode \'xor\' must have at least two src cells')

        code = []
        for src in src_list:
            code += [self.visit(('cond', src, ('add', dst - src, 1)))]

        code += [self.visit(('copy', work[0], dst, work[1]))]
        code += [self.visit(('iszero', work[0], work[1]))]
        #code += [self.visit((
        return code

    def visitIsZero(self, dst, src, negated=False):
        code = []
        if not negated:
            code += [self.visit(('add', dst, 1))]

        code += [self.visit(('cond', src, ('add', dst - src, 1 if negated else -1)))]
        return code

    def visitAdd(self, dst, count):
        return [self.visit(('go', dst))] + [('-' if count < 0 else '+') * abs(count)] + [self.visit(('go', dst * -1))]

    def visitCond(self, src, op):
        code = [self.visit(('go', src))]
        code += ['[']
        code += [self.visit(op)]
        code += [self.visit(('zero', 0))]
        code += [']']
        code += [self.visit(('go', src * -1))]
        return code

    def visitBranch(self, src, work, true_ops, false_ops):
        code = [self.visit(('go', src))]
        code += ['[']
        code += [self.visit(op) for op in true_ops]
        code += [self.visit(('add', work, 1))]
        code += [self.visit(('zero', 0))]
        code += [']']
        #code += [self.visit(('cond', work, false_op))]
    
    def generateMove(self, op, dst, src):
        code = [self.visit(('go', src))]
        code += ['[-']
        code += [self.visit(('go', dst - src))]
        code += [op]
        code += [self.visit(('go', src - dst))]
        code += [']']
        code += [self.visit(('go', src * -1))]
        return code

    def visitMove(self, dst, src):
        return self.generateMove('+', dst, src)

    def visitUnmove(self, dst, src):
        return self.generateMove('-', dst, src)

    def visitZero(self, dst):
        return [self.visit(('go', dst))] + ['[-]'] + [self.visit(('go', dst * -1))]

    def visitCopy(self, dst, src, work):
        code = [self.visit(('go', src))]
        code += ['[-']
        code += [self.visit(('go', work - src))]
        code += ['+']
        code += [self.visit(('go', dst - work))]
        code += ['+']
        code += [self.visit(('go', src - dst))]
        code += [']']

        code += [self.visit(('move', 0, work - src))]
        code += [self.visit(('go', src * -1))]
        return code

    def visitIsEq(self, dst, first, second, work):
        code += [self.visit(('go', work[0]))]
        code += ['+[']
        code += [self.visit(('copy', work_a - first, second - first, work_b))]
        code += [self.visit(('isnotzero', work_b, work_a - first))]
        code += [']']
        return code

    def visitBIL(self, bil):
        bf = []
        for c in bil:
            bf.append(self.visit(c))
        return bf


parser = CParser()

buf = r'''
    static void foo()
    {
        char x;
        if ('\x1') {
            x = '\x5';
            x = '\x3';
        }
    }
'''

#c_ast = parser.parse(buf, 'x.c')
#c_ast.show()
#print("#######")

#v = BytecodeVisitor()
#bytecode = v.visitMain(c_ast.ext[0])
#print('bytecode: ' + str(bytecode))

#labeled_bytecode = addLabels(bytecode)
#print('labeled bytecode: ' + str(labeled_bytecode))

#jump_bytecode = addJumps(labeled_bytecode)
#print('jump bytecode: ' + str(jump_bytecode))

#program = getProgram(labeled_bytecode)
#print('basic blocks: ' + str(program))

#bilVisitor = BILVisitor()
#bil = bilVisitor.visitBytecode(bytecode)
#print('bil: ' + str(bil))

bfVisitor = BrainfuckVisitor()
ops = [Add(1, 1), Add(2, 1), And(3, [1, 2])]
dump_ops(ops)
sys.exit(0)
#bf = bfVisitor.visitBIL([('add', 1, 1), ('add', 2, 1), ('and', 3, [1, 2], 4)])

print('bf:')
for pair in bf:
	pair.dump(0)

flat_bf = ''
for child in bf:
    flat_bf += child.flattened()

interp = BrainfuckInterpreter()
interp.execute(flat_bf, print_state=True, step=True)
