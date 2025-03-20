from lark import *
from lark.tree import Tree
from lark.lexer import Token
from ast import literal_eval
import numpy as np
from copy import deepcopy

from helpers import *
from show    import *
from type    import typeof_declaration

#########################################################################
#                                                                       #
# This file contains helper functions for liveness analysis.            #
# vars_statement, vars_declaration, vars_exp, etc., computes the set of #
# variables that a given statement, declaration, expression, etc.       #
# reads from, and the set that it writes to.                            #
#                                                                       #
# The result is two sets of pairs (variable_name,scope_id), such that   #
# variables that are given the same name are distinguished.             #
#                                                                       #
#########################################################################


def vars_statement(s,scoped_name_env,seen_scopes):
    rule = node_rule(s, "statement")
    match(rule):
        case ['lval', 'EQ', _]: # Assignment
            [lval,_,exp]    = s.children
            (l_reads, l_writes) = vars_lval(lval,scoped_name_env)
            e_reads             = vars_exp (exp, scoped_name_env)
            (R,W) = (l_reads.union(e_reads), l_writes)            
                
        case ['qupdate']:
            [qupdate] = s.children
            (R,W) = vars_qupdate(qupdate,scoped_name_env)
        
        case ['qupdate','IF',_]:  # Quantum update
            (qupdate,_,lval) = s.children
            (q_reads, q_writes) = vars_qupdate(qupdate,scoped_name_env)
            (c_reads, c_alsoreads) = vars_lval(lval,   scoped_name_env) # Here, both are read
            (R,W) = (q_reads.union(c_reads, c_alsoreads), q_writes)

        case ['MEASURE',_,_]: # qbit measurement
            [MEASURE,qbit,cbit]   = s.children
            (q_reads, q_writes) = vars_lval(qbit,scoped_name_env) # measure changes both
            (c_reads, c_writes) = vars_lval(cbit,scoped_name_env) # cbit and qbit
            (R,W) = (q_reads.union(c_reads), q_writes.union(c_writes))    

        case ['IF', _, 'statement', 'statement']:
            [IF,exp,stat_true, stat_false] = s.children
            e_reads             = vars_exp(exp,scoped_name_env)
            (t_reads, t_writes) = vars_statement(stat_true,scoped_name_env, seen_scopes)
            (f_reads, f_writes) = vars_statement(stat_false,scoped_name_env,seen_scopes)
            (R,W) = (e_reads.union(t_reads,f_reads), 
                     t_writes.union(f_writes))

        case ['WHILE', _, 'statement']:
            [WHILE,exp_test, stat] = s.children
            e_reads             = vars_exp(exp_test,scoped_name_env)
            (s_reads, s_writes) = vars_statement(stat,scoped_name_env,seen_scopes)
            (R,W) = (e_reads.union(s_reads), s_writes)
        
        case ['block']:
            [block] = s.children
            decls, stats = block.children
            
            block_scope = new_scope(scoped_name_env)
            block_env   = scoped_name_env + [block_scope]
            # We want to keep track of all the scopes we've seen in a "global" list
            seen_scopes.append(block_scope)            

            # This changes block_scope
            d_vars = [vars_declaration(d,block_env) for d in decls.children]
            #print(f"Block scope after declarations: {block_scope}")
            s_vars = [vars_statement(c,block_env,seen_scopes) for c in stats.children]

            v_reads  = set().union(*[v[0] for v in d_vars+s_vars])
            v_writes = set().union(*[v[1] for v in d_vars+s_vars])

            (R,W) = (v_reads, v_writes)

    return (R,W)

def vars_declaration(d,scoped_name_env):
    # vars_declaration both computes which variables are read and written
    # and updates the environment with the new variable declarations
    rule = node_rule(d, "declaration")
    (name,type) = typeof_declaration(d)

    match(rule):
        case ['TYPE','lval']: # Scalar variable declaration
            [_,lval] = d.children
            # First add the variable to the current scope, so it will resolve correctly
            scope = scoped_name_env[-1]
            scope[name] = (type,scope['?scope_id'])
            # Then look up the lval base, and variables referenced in its index expression

            R,W = vars_lval(lval,scoped_name_env)

        case ['TYPE','ID',_]: # Scalar variable with initial value
            [_,lval,exp] = d.children
            # First add the variable to the current scope, so it will resolve correctly
            scope = scoped_name_env[-1]
            scope[name] = (type,scope['?scope_id'])
            # Then look up the lval base, and variables referenced in its index expression
            (v_reads, v_writes) = vars_lval(lval,scoped_name_env)
            e_reads = vars_exp(exp,scoped_name_env)

            R,W = (v_reads.union(e_reads), v_writes)
        
        case ['TYPE','ID',_,'exps']: # Array variable with initial values
            [_,lval,e_size,exps] = d.children
            # First add the variable to the current scope, so it will resolve correctly
            scope = scoped_name_env[-1]
            scope[name] = (type,scope['?scope_id'])
            # Then look up the lval base, and variables referenced in its index expression
            (v_reads, v_writes) = vars_lval(lval,scoped_name_env)
            s_reads = vars_exp(e_size,scoped_name_env)
            # ...and the variables referenced in the initialization expressions
            e_reads = set().union(*[vars_exp(e,scoped_name_env) for e in exps.children])

            R,W = (v_reads.union(s_reads,e_reads), v_writes)
    
    return R,W


def vars_qupdate(qupdate,scoped_name_env):
    rule = node_rule(qupdate, "qupdate")
    # A quantum update reads from the index expressions
    # and writes to the qbit variables.
    match(rule):
        case ['gate', 'lval']:
            [gate,lval] = qupdate.children
            (g_reads, g_writes) = vars_lval(lval,scoped_name_env)
            R,W = (g_reads, g_writes)

        case ['lval','SWAP','lval']: 
            [lval1,_,lval2] = qupdate.children
            (v1_reads, v1_writes) = vars_lval(lval1,scoped_name_env)
            (v2_reads, v2_writes) = vars_lval(lval2,scoped_name_env)
            R,W = (v1_reads.union(v2_reads), v1_writes.union(v2_writes))            
    return (R,W)


def vars_lval(lval,scoped_name_env):
    if(not hasattr(lval, 'children')): # Assume we've been passed an ID token
        return (set(), set([scope_and_name(lval,scoped_name_env)]))
    
    rule = node_rule(lval, "lval")
    match(rule):
        case ['ID']: # Scalar variable node
            [var] = lval.children
            R,W = (set(), set([scope_and_name(var,scoped_name_env)]))

        case ['ID', _]: # Array element node
            [var,e1] = lval.children
            V1 = set([scope_and_name(var,scoped_name_env)])
            V2 = vars_exp(e1,scoped_name_env)
            R,W = (V2, V1)

    return (R,W)


def vars_exp(e,scoped_name_env):
    # Expressions will never write to variables, only read from them

    if(not hasattr(e, 'children')):
        match(node_name(e)):
            case 'ID': return set([scope_and_name(e,scoped_name_env)])
            case    _: return set()
    
    rule = node_rule(e, "exp")
        
    match(rule):
        case [_]: # Redundant exp node
           [exp] = e.children
           return vars_exp(exp,scoped_name_env)
        case ['UNOP', _] | ['BUILTIN_FUN1',_]:       # Unary operation node
            unop,exp = e.children
            return vars_exp(exp,scoped_name_env)

        case [_,'BINOP',_] | [_,'PE',_] | [_,'MD',_] | [_,'AS',_] | [_,'CMP',_]:  # Binary operation node
            exp1, binop, exp2 = e.children
            V1, V2 = vars_exp(exp1,scoped_name_env), vars_exp(exp2,scoped_name_env)
            return V1.union(V2)
        
        case ['BUILTIN_FUN2', _, _]: # Built-in function with two arguments
            fun, e1, e2 = e.children
            V1, V2 = vars_exp(e1,scoped_name_env), vars_exp(e2,scoped_name_env)
            return V1.union(V2)
        
        case ['ID']: # Scalar variable node
            [var] = e.children
            return set([scope_and_name(var,scoped_name_env)])

        case ['ID', _]: # Array element node
            [var,e1] = e.children

            V1 = set([scope_and_name(var,scoped_name_env)])
            V2 = vars_exp(e1,scoped_name_env)
            return V1.union(V2)
        case _:
            raise Exception(f"Unrecognized rule {rule} in exp {scoped_name_exp(e)}")        

