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
                raise Exception('Malformed go opcode %s: dst cannot be a SymbolicLocation with no value' % self)
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