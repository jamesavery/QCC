from lark import *
from lark.tree import Tree
from lark.lexer import Token
from ast import literal_eval
import numpy as np

from helpers import *

def showcq_program(P):
    ps = [showcq_procedure(p) for p in P.children]
    return '\n\n'.join(ps)

def showcq_procedure(p):
    rule = node_rule(p, "procedure")

    match(rule):
        case ['ID','parameter_declarations','statement']: 
            fname, params, stat = p.children
            sparams = [showcq_parameter_declaration(d) for d in params.children]
            sparams = ",".join(sparams)
            sstat   = showcq_statement(stat)
            return f"{fname}({sparams}){sstat}"
        
        case _: 
            raise Exception(f"Unrecognized rule {rule} in procedure {p}")

def showcq_parameter_declaration(d): 
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


def showcq_statement(s,depth=0):
    rule = node_rule(s, "statement")
    prefix = "  "*depth
    try:
        match(rule):
            case ['procedure_call']:   # Subroutine call
                [procedure_call] = s.children
                name, lvals = procedure_call.children
                return f"{prefix}call '{name}' ({', '.join([showcq_lval(v) for v in lvals.children])}) ;"
            
            case ['lval', 'EQ', _] | ['ID','EQ',_]: # Assignment
                [lval,_,exp]    = s.children
                lhs = showcq_lval(lval)
                rhs = showcq_exp(exp)
                return f"{prefix}{lhs} = {rhs} ;"
            
            case ['qupdate']:           # Quantum update
                [qupdate]       = s.children
                sc = showcq_qupdate(qupdate)
                return f"{prefix}{sc} ;"

            case ['qupdate','IF',_]:# Conditional quantum update
                [qupdate,_,lval] = s.children
                sq, sc = showcq_qupdate(qupdate), showcq_lval(lval)
                return f"{prefix}{sq} if {sc}) ;"

            case ['MEASURE',_,_]: # qbit measurement
                [_,qbit,cbit]   = s.children
                sq, sc = showcq_lval(qbit), showcq_lval(cbit)
                return f"{prefix}measure {sq} -> {sc} ;"

            case ['IF', _, 'statement', 'statement']:
                [_,exp,stat_true, stat_false] = s.children
                se, st, sf = showcq_exp(exp), showcq_statement(stat_true,depth+1), showcq_statement(stat_false,depth+1)
                return f"{prefix}if({se})\n{st}\nelse\n{sf}"

            case ['WHILE', _, 'statement']:
                [_,exp_test, stat] = s.children
                se, st = showcq_exp(exp_test), showcq_statement(stat,depth+1)
                se, st = showcq_exp(exp_test), showcq_statement(stat,depth+1)
                return f"{prefix}while({se})\n{st}"

            case ['block']:
                [block] = s.children
                decls, stats = block.children

                if(stats == []): return "{}"
                
                sdecls = [showcq_declaration(d,depth+1) for d in decls.children]
                sstats = [showcq_statement(c,depth+1) for c   in stats.children]
                sdecls = "\n".join(sdecls)  
                sstats = "\n".join(sstats)  
                decsep = "\n" if len(decls.children)>0 else ""
                
                return f"{prefix}{{\n{sdecls}{decsep}{sstats}\n{prefix}}}\n"
            
            case _: 
                raise Exception(f"Unrecognized rule: {rule} in statement {s}")
    except:        
        raise Exception(f"Error evaluating rule {rule} for node {s}") 



def showcq_exp(e, depth=0, debug=0):
    # Is this a terminal (a leaf node), or does e have children?
    
    match(node_name(e)):
        case 'NUMERICAL_VALUE': return f"{e}"
        case 'INT':             return f"{e.value}"
        case 'FLOAT':           return f"{e.value}"
        case 'NAMED_CONSTANT':  return f"{e.value}"
    
    # e has children to process, extract pattern:
    rule = node_rule(e, "exp")
        
    if(debug): 
        print(f"{' '*depth}",depth, rule)
    
    match(rule):
        # case [_]: # Redundant exp node
        #     [exp] = e.children
        #     return showcq_exp(exp,depth+1)
        case ['UNOP', _]:       # Unary operation node
            unop,exp = e.children
            s1 = showcq_exp(exp,depth+1)
            return f"({unop} {s1})"

        case [_,'BINOP',_] | [_,'PE',_] | [_,'MD',_] | [_,'AS',_] | [_,'CMP',_]:  # Binary operation node
            exp1, binop, exp2 = e.children
            s1, s2 = showcq_exp(exp1,depth+1), showcq_exp(exp2,depth+1)
            return f"({s1} {binop} {s2})"

        case ['BUILTIN_FUN1', _]: # Built-in function with one argument
            fun, e1 = e.children
            s1 = showcq_exp(e1,depth+1)
            return f"{fun}({s1})"
        
        case ['BUILTIN_FUN2', _, _]: # Built-in function with two arguments
            fun, e1, e2 = e.children
            s1, s2 = showcq_exp(e1,depth+1), showcq_exp(e2,depth+1)
            return f"{fun}({s1},{s2})"
        
        case ['ID']: # Scalar variable node
            [var] = e.children
            return f"{var}"

        case ['ID', _]: # Array element node
            [var,e1] = e.children
            v1 = showcq_exp(e1,depth+1)
            return f"{var}[{v1}]"
        
    raise Exception(f"{rule} pattern not implemented in {e.pretty()}")


def showcq_declaration(d,depth=0):
    rule = node_rule(d, "declaration")
    prefix = "  "*depth
    match(rule):
        case ['TYPE',_]:     # Scalar or array-declaration without initialization (0-initialize)
            type, lval = d.children
            return f"{prefix}{type} {showcq_lval(lval)} ;"
        
        case ['TYPE','ID',_]: # Scalar declaration with initialization
            type, name, exp = d.children
            sexp = showcq_exp(exp)
            return f"{prefix}{type} {name} = {sexp} ;"
        
        case ['TYPE','ID',_,'exps'] | ['TYPE','ID','INT','exps']: # Array declaration with initialization 
            type, name, exp_index, values = d.children
            sindex = showcq_exp(exp_index)            
            svalues = [showcq_exp(e) for e in values.children]
            svalues = ",".join(svalues)
            return f"{prefix}{type} {name}[{sindex}] = [{svalues}] ;"
        
        case _: 
            raise Exception(f"Unrecognized rule {rule} in declaration {d}")                    

def showcq_lval(v):
    if not hasattr(v, 'children'): return f"{v}" # Allow IDs to be lvals

    rule = node_rule(v, "lval")

    match(rule):
        case ['ID']: # Scalar variable
            [var_name] = v.children
            return f"{var_name}"
                            
        case ['ID', _]: # Array variable
            [var_name,exp] = v.children
            return f"{var_name}[{showcq_exp(exp)}]"


def showcq_qupdate(q):
    rule = node_rule(q, "qupdate")
    
    match(rule):
        case ['gate',_]:  # Single-qubit gate
            [gate, lval] = q.children
            s1, s2 = showcq_gate(gate), showcq_lval(lval)
            return f"{s1} {s2}"
        
        case [_,'SWAP',_]: # Array variable
            [lval1,_,lval2] = q.children
            s1, s2 = showcq_lval(lval1), showcq_lval(lval2)
            return f"{s1} <> {s2}"

def showcq_gate(g):
    rule = node_rule(g, "gate")
    
    match(rule):
        case ['NOT']:
            return "not"
        case ["H"]:
            return "H"
        case ["rgate",_]:
            rgate, angle_exp = g.children
            [R] = rgate.children
            se = showcq_exp(angle_exp)
            return f"{R}({se})"
        case _:
            raise Exception(f"Unrecognized rule {rule} in gate {g}")


