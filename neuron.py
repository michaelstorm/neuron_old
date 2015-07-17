import traceback
import sys
from interp import BrainfuckInterpreter
from cast import CASTVisitor, addJumps, addLabels, getProgram
from pycparser.c_parser import CParser
from bil import BILVisitor
from bf_out import BrainfuckVisitor


__author__ = 'Michael Storm'


def print_bytecode(bytecode):
    for code in bytecode:
        if code[0] == 'label':
            print('%s:' % code[1])
        else:
            print('\t%s' % ' '.join([str(c) for c in code]))


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

c_ast = parser.parse(buf, 'x.c')
c_ast.show()
print("#######")

v = CASTVisitor()
bytecode = v.visitMain(c_ast.ext[0])
print('\nbytecode: ' + str(bytecode))

labeled_bytecode = addLabels(bytecode)
print('\nlabeled bytecode:')
print_bytecode(labeled_bytecode)

jump_bytecode = addJumps(labeled_bytecode)
print('\njump bytecode:')
print_bytecode(jump_bytecode)

program = getProgram(labeled_bytecode)
print('\nbasic blocks: ' + str(program))

bilVisitor = BILVisitor()
bil = bilVisitor.visitProgram(program)
# bil = bilVisitor.visitBytecode(labeled_bytecode)
print('\nbil: ')
print_bytecode(bil)

# ops = [Add(1, 1), Add(2, 1), And(3, [1, 2])]

# print('\nops:')
# dump_ops(ops)

bfVisitor = BrainfuckVisitor()
bf = bfVisitor.visitBIL(bil)
print('\nbf:')
for pair in bf:
	pair.dump(0)

flat_bf = ''
for child in bf:
    flat_bf += child.flattened()

interp = BrainfuckInterpreter()
interp.execute(flat_bf, print_state=True, step=True)
