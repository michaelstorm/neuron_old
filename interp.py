import sys

class BrainfuckInterpreter(object):

    def __init__(self, size=30000):
        self.cells = [0] * size
        self.pointer = 0
        self.loop_stack = []
        self.farthest_nonzero = 0

    def execute(self, bf, print_state=False, step=False):
        i = 0
        while i < len(bf):
            opcode = bf[i]

            if print_state:
                print((' ' * i) + 'v')
                print(bf)
                self.dump_cells()

            if opcode == '>':
                self.pointer += 1
            elif opcode == '<':
                self.pointer -= 1
                if self.pointer < 0:
                    raise Exception('Negative pointer at index ' + str(i))
            elif opcode == '+':
                self.cells[self.pointer] += 1
                if self.cells[self.pointer] != 0 \
                and self.pointer > self.farthest_nonzero:
                    self.farthest_nonzero = self.pointer
            elif opcode == '-':
                self.cells[self.pointer] -= 1
                if self.pointer == self.farthest_nonzero:
                    while self.farthest_nonzero > 0 \
                    and self.cells[self.farthest_nonzero] == 0:
                        self.farthest_nonzero -= 1
            elif opcode == '[':
                if self.cells[self.pointer] == 0:
                    loop_counter = 1
                    while loop_counter > 0:
                        i += 1
                        if bf[i] == '[':
                            loop_counter += 1
                        elif bf[i] == ']':
                            loop_counter -= 1
                else:
                    self.loop_stack.append(i)
            elif opcode == ']':
                i = self.loop_stack.pop() - 1
            elif opcode == '.':
                print(chr(self.cells[self.pointer]), end='')
            elif opcode == ',':
                self.cells[self.pointer] = sys.stdin.read(1)
            else:
                raise Exception('Unrecognized opcode ' + opcode)

            i += 1
            if step:
                while sys.stdin.read(1) != '\n':
                    pass

            if print_state and not step:
                print()

        if print_state:
            print((' ' * i) + 'v')
            print(bf)
            self.dump_cells()

    def dump_cells(self, until=None):
        if until is None:
            until = max(self.farthest_nonzero, self.pointer)

        print(self.loop_stack)
        i = 0
        while i <= until:
            if self.pointer == i:
                print('>{}< '.format(self.cells[i]), end='')
            else:
                print('[{}] '.format(self.cells[i]), end='')
            i += 1
        print()
