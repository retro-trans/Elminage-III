"""Derive script opcode operand signatures from the EBOOT dispatcher (0x0888F074).

Writes work/source/scp_sigs.json: {op: [steps]}, step = ['ARGS', n] | ['STR'] | ['RAW', n] | ['U8'] | ['?', addr]
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mips import Elf

e = Elf()
JT = 0x08953100; NOPS = 0x13a
EXITS = {0x088934ac, 0x088934b0, 0x088934a8}
ARGS, RAW, U8, OP, GETARG, STRSTART, STRPARSE = 0x08893678, 0x08893808, 0x08893614, 0x08893628, 0x08893664, 0x08894270, 0x08897804
BENIGN = {GETARG, STRSTART}
memo = {}

def a1_before(ins, k):
    val = None
    for j in list(range(max(0, k - 8), k)) + [k + 1]:
        if j < len(ins):
            i = ins[j]
            if i.mnemonic in ('addiu', 'ori') and i.op_str.startswith('$a1, $zero,'):
                val = int(i.op_str.split(',')[-1].strip(), 0)
            elif i.op_str.startswith('$a1,') and j < k:
                val = None if i.mnemonic not in ('addiu', 'ori') else val
    return val

def scan(start, is_func, depth=0):
    key = (start, is_func)
    if key in memo:
        return memo[key]
    memo[key] = []
    steps = []
    ins = e.insns(start, 600)
    for k, i in enumerate(ins):
        m = i.mnemonic
        if m == 'jal':
            t = int(i.op_str, 16)
            if t == ARGS:
                steps.append(['ARGS', a1_before(ins, k)])
            elif t == RAW:
                steps.append(['RAW', a1_before(ins, k)])
            elif t == U8:
                steps.append(['U8'])
            elif t == OP:
                steps.append(['U16X'])
            elif t == STRPARSE:
                # inline only if a2 = read pointer (lw $a2, 0x528(...)) shortly before
                inline = any(ins[j].mnemonic == 'lw' and ins[j].op_str.startswith('$a2, 0x528(')
                             for j in range(max(0, k - 8), k))
                if inline:
                    steps.append(['STR'])
            elif t in BENIGN:
                pass
            elif depth < 3 and 0x08804000 <= t < 0x0894d8d0:
                sub = scan(t, True, depth + 1)
                steps += sub
        if not is_func and m in ('b', 'j') and int(i.op_str, 16) in EXITS:
            break
        if not is_func and m == 'beq' and i.op_str.startswith('$zero, $zero'):
            break
        if is_func and m == 'jr' and i.op_str == '$ra':
            break
    memo[key] = steps
    return steps

tab = [e.u32(JT + i * 4) for i in range(NOPS)]
default = max(set(tab), key=tab.count)
out = {}
for op, t in enumerate(tab):
    if t == default:
        out['%03x' % op] = None
    else:
        out['%03x' % op] = scan(t, False)
root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
json.dump(out, open(os.path.join(root, 'work', 'source', 'scp_sigs.json'), 'w'), indent=0)
for k, v in out.items():
    if v:
        print(k, v)
