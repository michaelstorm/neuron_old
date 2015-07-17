class BILVisitor(object):

    def __init__(self):
        self.stack = {}
        self.stack_depth = 0

    def visitProgram(self, program):
        label_nums = {}
        last_label_num = 1
        label_nums[program.main] = last_label_num
        for label in program.blocks:
            if label is not program.main:
                last_label_num += 1
                label_nums[label] = last_label_num

        #code = [('add', 0, 1), ('while'), ('add', 0, -1)]
        code = []
        for label in program.blocks:
            code.extend(self.visitBytecode(program.blocks[label].instrs))
        return code

    def visit(self, c):
        print('visiting', c[0], 'stack:', self.stack)
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
        # stack layout: [block number] [reserved variables] [workspace]
        self.stack[c[1]] = self.stack_depth
        self.stack_depth += c[2]
        return [('go', c[2])]

    def visitUnreserve(self, c):
        self.stack_depth -= c[2]
        del self.stack[c[1]]
        return [('go', c[2] * -1)]

    def visitPop(self, c):
        # move the value at the top of the stack to the destination specified
        # by the argument, which will be a reserved location lower in the stack
        print('stack:', self.stack)
        bc = [('left', 1), ('move', self.stack[c[1]] - self.stack_depth + 1, 0)]
        self.stack_depth -= 1
        return bc

    def visitPush(self, c):
        # if the first argument is numeric
        if c[1][0].isdigit() or c[1][0] == '-':
            # if it's a char-sized constant
            if c[1][-1] == 'c':
                self.stack_depth += 1
                return [('plus', 0, int(c[1][0:-1])), ('go', 1)]
            else:
                raise Exception('Unsupported constant ' + c[1])
        else:
            raise Exception('Unsupported push operand ' + c[1])

    def visitAddC(self, c):
        # add the value at the top of the stack to the value at the location
        # immediately lower in the stack
        self.stack_depth -= 1
        return [('move', -2, -1)]

    def visitSubC(self, c):
        # subtract the value at the top of the stack from the value at the
        # location immediately lower in the stack
        self.stack_depth -= 1
        return [('unmove', -2, -1)]

    def visitBytecode(self, code):
        bil = []
        for c in code:
            bil.extend(self.visit(c))
        return bil