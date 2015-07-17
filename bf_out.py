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