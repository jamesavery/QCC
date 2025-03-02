from lark import *
from lark.tree import Tree
from lark.lexer import Token
from ast import literal_eval
import numpy as np

from helpers import *

def show_program(P):
    ps = [show_procedure(p) for p in P.children]
    return '\n\n'.join(ps)

def show_procedure(p):
    rule = node_rule(p, "procedure")

    match(rule):
        case ['ID','parameter_declarations','statement']: 
            fname, params, stat = p.children
            sparams = [show_parameter_declaration(d) for d in params.children]
            sparams = ",".join(sparams)
            sstat   = show_statement(stat)
            return f"{fname}({sparams}){sstat})"
        
        case _: 
            raise Exception(f"Unrecognized rule {rule} in procedure {p}")

def show_parameter_declaration(d): 
    rule = node_rule(d, "parameter_declaration")
    
    match(rule): 
        case ['TYPE','ID']:        # Scalar declaration
            type, name = d.children
            return f"{type} {name}"
        
        case ['TYPE','ID','INT']:  # Constant size array 
            type, name, size = d.children
            return f"{type} {name}[{size}]"
        
        case ['TYPE','ID','ID']:   # Variable size array
            type, name, size = d.children
            return f"{type} {name}[{size}]"
                    
        case _: 
            raise Exception(f"Unrecognized rule {rule} in parameter_declaration {d}")        


def show_statement(s):
    rule = node_rule(s, "statement")
    
    try:
        match(rule):
            case ['procedure_call']:   # Subroutine call
                [procedure_call] = s.children
                name, lvals = procedure_call.children
                return f"call '{name}' ({', '.join([show_lval(v) for v in lvals.children])}) ;"
            
            case ['lval', 'EQ', _] | ['ID','EQ',_]: # Assignment
                [lval,_,exp]    = s.children
                lhs = show_lval(lval)
                rhs = show_exp(exp)
                return f"{lhs} = {rhs} ;"
            
            case ['qupdate']:           # Quantum update
                [qupdate]       = s.children
                return show_qupdate(qupdate)

            case ['qupdate','IF',_]:# Conditional quantum update
                [qupdate,_,lval] = s.children
                sq, sc = show_qupdate(qupdate), show_lval(lval)
                return f"{sc} if {sq}) ;"

            case ['MEASURE',_,_]: # qbit measurement
                [_,qbit,cbit]   = s.children
                sq, sc = show_lval(qbit), show_lval(cbit)
                return f"measure {sq} -> {sc} ;"

            case ['IF', _, 'statement', 'statement']:
                [_,exp,stat_true, stat_false] = s.children
                se, st, sf = show_exp(exp), show_statement(stat_true), show_statement(stat_false)
                return f"if({se})\n{st}\nelse\n{sf}"

            case ['WHILE', _, 'statement']:
                [_,exp_test, stat] = s.children
                se, st = show_exp(exp_test), show_statement(stat)
                return f"while({se})\n{st}"

            case ['block']:
                [block] = s.children
                decls, stats = block.children
                
                sdecls = [show_declaration(d) for d in decls.children]
                sstats = [show_statement(c) for c   in stats.children]
                sdecls = "\n".join(sdecls)  
                sstats = "\n".join(sstats)  
                return f"{{\n{sdecls}\n{sstats}\n}}\n"
            
            case _: 
                raise Exception(f"Unrecognized rule: {rule} in statement {s}")
    except:        
        raise Exception(f"Error evaluating rule {rule} for node {s}") 


def show_exp(e):
    # Is this a terminal (a leaf node), or does e have children?
    match(node_name(e)):
        case 'INT' | 'FLOAT': return f"/*{node_name(e)}*/{e.value}\n"
            
    # e has children to process, extract pattern:
    try:
        rule  = [node_name(c) for c in e.children]
    except:
        raise f"AST error in {e.pretty()}"
        
    
    match(rule):
        case ['exp']:
            [e1] = e.children
            return f"{show_exp(e1)}" 

        case ['INT'] | ['FLOAT'] | ['NAMED_CONSTANT']:
            [c] = e.children
            return f"{c.value}"
        
        case ['lval']:
            return show_lval(e.children[0])
        
        case ['UNOP', 'exp']:       # Unary operatio`n node
            unop,e1 = e.children
            s1 = show_exp(e1)
            return f"({unop} {s1})"

        case ['exp','BINOP','exp']:  # Binary operation node
            exp1, binop, exp2 = e.children
            s1, s2 = show_exp(exp1), show_exp(exp2)
            return f"({s1} {binop} {s2})"

        case ['BUILTIN_FUN1', 'exp']: # Built-in function with one argument
            fun, e1 = e.children
            s1 = show_exp(e1)
            return f"{fun}({s1})"
        
        case ['BUILTIN_FUN2', 'exp', 'exp']: # Built-in function with two arguments
            fun, e1, e2 = e.children
            s1, s2 = show_exp(e1), show_exp(e2)
            return f"{fun}({s1},{s2})"
        
    raise BaseException(f"{rule} pattern not implemented in {e.pretty()}")


def show_declaration(d):
    rule = node_rule(d, "declaration")
    
    match(rule):
        case ['TYPE',_]:     # Scalar or array-declaration without initialization (0-initialize)
            type, lval = d.children
            return f"{type} {show_lval(lval)}) ;"
        
        case ['TYPE','ID',_]: # Scalar declaration with initialization
            type, name, exp = d.children
            sexp = show_exp(exp)
            return f"{type} {name} = {sexp} ;"
        
        case ['TYPE','ID',_,'exps'] | ['TYPE','ID','INT','exps']: # Array declaration with initialization 
            type, name, exp_index, values = d.children
            sindex = show_exp(exp_index)            
            svalues = [show_exp(e) for e in values.children]
            svalues = ",".join(svalues)
            return f"{type} {name}[{sindex}] = [{svalues}] ;"
        
        case _: 
            raise Exception(f"Unrecognized rule {rule} in declaration {d}")                    

def show_lval(v):
#    if not hasattr(v, 'children'): return f"{v}" # Allow IDs to be lvals

    rule = node_rule(v, "lval")

    match(rule):
        case ['ID']: # Scalar variable
            [var_name] = v.children
            return f"{var_name}"
                            
        case ['ID', _]: # Array variable
            [var_name,exp] = v.children
            return f"{var_name}[{show_exp(exp)}]"


def show_qupdate(q):
    rule = node_rule(q, "qupdate")
    
    match(rule):
        case ['gate',_]:  # Single-qubit gate
            [gate, lval] = q.children
            s1, s2 = show_gate(gate), show_lval(lval)
            return f"{s1} {s2}"
        
        case [_,'SWAP',_]: # Array variable
            [lval1,_,lval2] = q.children
            s1, s2 = show_lval(lval1), show_lval(lval2)
            return f"{s1} <> {s2}"

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


