from itertools import chain
from pycparser.c_ast import FuncDef, ArrayDecl, Decl, While, Compound, Assignment, Constant, BinaryOp, If
import re

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


class CASTVisitor(object):

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
        stack = CASTVisitor.stackVisitor.visitFuncDef(f)
        print('stack: ' + str(stack))

        for name in stack.names():
            size = stack.size(name)
            code.append(('reserve', name, size))

        code.extend(self.visit(f.body))

        for name in stack.names():
            size = stack.size(name)
            code.append(('unreserve', name, size))

        return code


def addLabels(bytecode):
    label_num = 0

    def make_label():
        nonlocal label_num
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