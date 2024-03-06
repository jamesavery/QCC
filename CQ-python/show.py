from lark import *
from lark.tree import Tree
from lark.lexer import Token
from ast import literal_eval
import numpy as np

from helpers import *

def show_program(P):
    ps = [show_procedure(p) for p in P.children]
    return f"program([{','.join(ps)}])"

def show_procedure(p):
    rule = node_rule(p, "procedure")

    match(rule):
        case ['ID','parameter_declarations','statement']: 
            fname, params, stat = p.children
            sparams = [show_parameter_declaration(d) for d in params.children]
            sparams = ",".join(sparams)
            sstat   = show_statement(stat)
            return f"procedure({fname},\n[{sparams}],\n{sstat})"
        
        case _: 
            raise Exception(f"Unrecognized rule {rule} in procedure {p}")

def show_parameter_declaration(d): 
    rule = node_rule(d, "parameter_declaration")
    
    match(rule): 
        case ['TYPE','ID']:        # Scalar declaration
            type, name = d.children
            return f"{type}({name})"
        
        case ['TYPE','ID','INT']:  # Constant size array 
            type, name, size = d.children
            return f"{type}({name}[{size}])"
        
        case ['TYPE','ID','ID']:   # Variable size array
            type, name, size = d.children
            return f"{type}({name}[{size}])"
                    
        case _: 
            raise Exception(f"Unrecognized rule {rule} in parameter_declaration {d}")        


def show_statement(s):
    rule = node_rule(s, "statement")
    
    try:
        match(rule):
            case ['procedure_call']:   # Subroutine call
                [procedure_call] = s.children
                name, lvals = procedure_call.children
                return f"call('{name}', {[show_lval(v) for v in lvals.children]})"
            
            case ['lval', 'EQ', _]: # Assignment
                [lval,_,exp]    = s.children
                lhs = show_lval(lval)
                rhs = show_exp(exp)
                return f"assign({lhs},{rhs})"
            
            case ['qupdate']:           # Quantum update
                [qupdate]       = s.children
                return show_qupdate(qupdate)

            case ['qupdate','IF',_]:# Conditional quantum update
                [qupdate,_,lval] = s.children
                sq, sc = show_qupdate(qupdate), show_lval(lval)
                return f"conditional({sc},{sq})"

            case ['MEASURE',_,_]: # qbit measurement
                [_,qbit,cbit]   = s.children
                sq, sc = show_lval(qbit), show_lval(cbit)
                return f"measure({sq},{sc})"

            case ['IF', _, 'statement', 'statement']:
                [_,exp,stat_true, stat_false] = s.children
                se, st, sf = show_exp(exp), show_statement(stat_true), show_statement(stat_false)
                return f"if({se},\n{st},\n{sf})"

            case ['WHILE', _, 'statement']:
                [_,exp_test, stat] = s.children
                se, st = show_exp(exp_test), show_statement(stat)
                return f"while({se},\n{st})"

            case ['block']:
                [block] = s.children
                decls, stats = block.children
                
                sdecls = [show_declaration(d) for d in decls.children]
                sstats = [show_statement(c) for c   in stats.children]
                sdecls = ",\n".join(sdecls)  
                sstats = ",\n".join(sstats)  
                return f"block([{sdecls}],[{sstats}])"
            
            case _: 
                raise Exception(f"Unrecognized rule: {rule} in statement {s}")
    except:        
        raise Exception(f"Error evaluating rule {rule} for node {s}") 


def show_exp(e, depth=0, debug=0):
    # Is this a terminal (a leaf node), or does e have children?
    
    match(node_name(e)):
        case 'NUMERICAL_VALUE': return f"{type(e)}({e}`)"
        case 'INT':             return f"int({e.value})"
        case 'FLOAT':           return f"float({e.value})"
        case 'NAMED_CONSTANT':  return f"const({e.value})"
    
    # e has children to process, extract pattern:
    rule = node_rule(e, "exp")
        
    if(debug): 
        print(f"{' '*depth}",depth, rule)
    
    match(rule):
        # case [_]: # Redundant exp node
        #     [exp] = e.children
        #     return show_exp(exp,depth+1)
        case ['UNOP', _]:       # Unary operation node
            unop,exp = e.children
            s1 = show_exp(exp,depth+1)
            return f"unop('{unop}',{s1})"

        case [_,'BINOP',_] | [_,'PE',_] | [_,'MD',_] | [_,'AS',_] | [_,'CMP',_]:  # Binary operation node
            exp1, binop, exp2 = e.children
            s1, s2 = show_exp(exp1,depth+1), show_exp(exp2,depth+1)
            return f"binop({s1},'{binop}',{s2})"

        case ['BUILTIN_FUN1', _]: # Built-in function with one argument
            fun, e1 = e.children
            s1 = show_exp(e1,depth+1)
            return f"builtin1('{fun}',{s1})"
        
        case ['BUILTIN_FUN2', _, _]: # Built-in function with two arguments
            fun, e1, e2 = e.children
            s1, s2 = show_exp(e1,depth+1), show_exp(e2,depth+1)
            return f"builtin2('{fun}',{s1},{s2})"
        
        case ['ID']: # Scalar variable node
            [var] = e.children
            return f"var('{var}')"

        case ['ID', _]: # Array element node
            [var,e1] = e.children
            v1 = show_exp(e1,depth+1)
            return f"array_element('{var}',{v1})"
        
    raise Exception(f"{rule} pattern not implemented in {e.pretty()}")


def show_declaration(d):
    rule = node_rule(d, "declaration")
    
    match(rule):
        case ['TYPE','lval']:     # Scalar or array-declaration without initialization (0-initialize)
            type, lval = d.children
            return f"declare_scalar({type}, {show_lval(lval)})"
        
        case ['TYPE','ID',_]: # Scalar declaration with initialization
            type, name, exp = d.children
            sexp = show_exp(exp)
            return f"initialize_{type}({name},{sexp})"
        
        case ['TYPE','ID',_,'exps']: # Array declaration with initialization
            type, name, exp_index, values = d.children
            sindex = show_exp(exp_index)            
            svalues = [show_exp(e) for e in values.children]
            svalues = ",".join(svalues)
            return f"initialize_{type}_array({name}[{sindex}], [{svalues}])"
        
        case _: 
            raise Exception(f"Unrecognized rule {rule} in declaration {d}")                    

def show_lval(v):
    if not hasattr(v, 'children'): return f"{v}" # Allow IDs to be lvals    
    rule = node_rule(v, "lval")

    match(rule):
        case ['ID']: # Scalar variable
            [var_name] = v.children
            return f"lval({var_name})"
                            
        case ['ID', _]: # Array variable
            [var_name,exp] = v.children
            return f"lval_elem({var_name}, {show_exp(exp)})"


def show_qupdate(q):
    rule = node_rule(q, "qupdate")
    
    match(rule):
        case ['gate','lval']:  # Single-qubit gate
            [gate, lval] = q.children
            s1, s2 = show_gate(gate), show_lval(lval)
            return f"gate({s1}, {s2})"
        
        case ['lval','SWAP','lval']: # Array variable
            [lval1,_,lval2] = q.children
            s1, s2 = show_lval(lval1), show_lval(lval2)
            return f"swap({s1},{s2})"

def show_gate(g):
    rule = node_rule(g, "gate")
    
    match(rule):
        case ['NOT']:
            return "not"
        case ["H"]:
            return "H"
        case ["rgate",_]:
            rgate, angle_exp = g.children
            [R] = rgate.children
            se = show_exp(angle_exp)
            return f"{R}({se})"
        case _:
            raise Exception(f"Unrecognized rule {rule} in gate {g}")


