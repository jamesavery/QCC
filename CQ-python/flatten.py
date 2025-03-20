from lark import *
from lark.tree import Tree
from lark.lexer import Token
from ast import literal_eval
import numpy as np
from copy import deepcopy

from helpers import *
from show    import *
from type    import typeof_declaration
from vars    import *

#########################################################################
#                                                                       #
# This file contains helper functions for flattening scopes.            #
# flatten_statement computes unique names for all variable declarations # 
# and references in expressions, and rewrites all declarations and      # 
# references to use the unique names. After this, all nested blocks are #
# flattened into a top-level block, with all variables declared at the  #
# top (now uniquely named), and no nested blocks.                       #
# If while-loops, calls,  and if-conditionals have been PE'd away,      #
# this yields a flat list of statements.                                #
#                                                                       #
#########################################################################

def flatten_program(P):
    main = P.children[0]
    result = deepcopy(P)
    result.children = [flatten_procedure(main)]
    return result

def flatten_procedure(p):
    [name, params, stat] = p.children
    scoped_name_env = [{'?scope_id_max': 0, '?scope_id': 0}]
    seen_scopes = []
    
    # First, we need to add the parameters to the current scope
    p_vars = [vars_declaration(d,scoped_name_env) for d in params.children]
    #print(f"Procedure scope after parameters: {scoped_name_env[-1]}")

    # Get all variables read and written in the procedure, so we can declare them at the top
    (R,W) = vars_statement(stat,scoped_name_env,seen_scopes)

    # print(f"Procedure scope after statements: {scoped_name_env[-1]}")
    # print(f"Seen scopes: {seen_scopes}")
    # print(f"Procedure reads from variables: {R}")
    # print(f"Procedure writes to variables: {W}")

    # Build the declarations using the type information from all the seen scopes:
    flat_declarations = []
    for scope in seen_scopes:
        for var in scope:
            if(var[0] != '?'):
                (type,scope_id) = scope[var]
                flat_declarations.append(make_declaration(type,f"{var}_{scope_id}"))

    unique_statement = scoped_name_statement(stat, scoped_name_env)

    flat_statements = flatten_statement(unique_statement,'block')

    # print(f"Flattened procedure statements:")
    # for c in flat_statements:

    # print(f"Flattened declarations:")
    # for d in flat_declarations:
    

    return make_procedure(name, params.children,
                          make_block(flat_declarations, flat_statements))


# flatten_statement takes a statement with only unique names and returns a flattened list of statements
def flatten_statement(s,parent_statement):
    rule = node_rule(s, "statement")
    match(rule): 
        # 3 types of statements can contain nested sub-blocks
        case ['block']:
            [block] = s.children
            _, stats = block.children # Declarations have already been flattened
            # If parent is a loop or conditional, we can't flatten the block
            flat_stats = sum([flatten_statement(c,'block') for c in stats.children],[])
            #print(f"flat_stats = {flat_stats}")
            if parent_statement == 'block':
                return flat_stats
            else:
                return [make_block([],flat_stats)]
        
        case ['IF', _, 'statement', 'statement']:
            [IF,exp,stat_true, stat_false] = s.children
            flat_true  = flatten_statement(stat_true,'IF')
            flat_false = flatten_statement(stat_false,'IF')
            new_true   = flat_true[0]  if len(flat_true)  == 1 else make_block([],flat_true)
            new_false  = flat_false[0] if len(flat_false) == 1 else make_block([],flat_false)
            return [make_if(exp,new_true,new_false)]

        case ['WHILE', _, 'statement']:
            [WHILE,exp_test, stat] = s.children
            flat_stat = flatten_statement(stat,'WHILE')
            new_stat  = flat_stat[0] if len(flat_stat) == 1 else make_block([],flat_stat)
            return [make_while(exp_test,new_stat)]

        # The remaining statements we just return as is
        case _:
            return [s]

    


def scoped_name_lval(lval,scoped_name_env):
    if(not hasattr(lval, 'children')): # Assume we've been passed an ID token
        return Token('ID',scoped_name(lval,scoped_name_env))
    
    result = deepcopy(lval)
    rule = node_rule(lval, "lval")
    match(rule):
        case ['ID']: # Scalar variable node
            [var] = lval.children
            name = scoped_name(var,scoped_name_env)
            result.children = [Token('ID', name)]

        case ['ID', _]: # Array element node
            [var,e1] = lval.children
            name = scoped_name(var,scoped_name_env)
            V2 = scoped_name_exp(e1,scoped_name_env)
            
            result.children = [Token('ID', name),V2]
    
    return result


def scoped_name_exp(e,scoped_name_env):
    # Expressions will never write to variables, only read from them

    if(not hasattr(e, 'children')):
        match(node_name(e)):
            case 'ID': 
                return make_exp([make_lval(scoped_name(e,scoped_name_env))])
            case    _: return deepcopy(e)

    rule = node_rule(e, "exp")
    result = deepcopy(e)
    
    match(rule):
        case [_]: # Redundant exp node
           [exp] = e.children
           return scoped_name_exp(exp,scoped_name_env)
        case ['UNOP', _] | ['BUILTIN_FUN1',_]:       # Unary operation node
            unop,exp = e.children
            scoped_exp = scoped_name_exp(exp,scoped_name_env)
            result.children = [unop,scoped_exp]
        
        case [_,'BINOP',_] | [_,'PE',_] | [_,'MD',_] | [_,'AS',_] | [_,'CMP',_]:  # Binary operation node
            exp1, binop, exp2 = e.children
            V1, V2 = scoped_name_exp(exp1,scoped_name_env), scoped_name_exp(exp2,scoped_name_env)
            result.children = [V1, binop, V2]
        
        case ['BUILTIN_FUN2', _, _]: # Built-in function with two arguments
            fun, e1, e2 = e.children
            V1, V2 = scoped_name_exp(e1,scoped_name_env), scoped_name_exp(e2,scoped_name_env)
            result.children = [fun, V1, V2]
        
        case ['ID']: # Scalar variable node
            [var] = result.children
            name = scoped_name(var,scoped_name_env)
            result.children[0] = Token('ID', name)

        case ['ID', _]: # Array element node
            [var,e1] = result.children

            name = scoped_name(var,scoped_name_env)
            V2 = scoped_name_exp(e1,scoped_name_env)
            result.children[0] = Token('ID', name)
            result.children[1] = V2
        case _:
            raise Exception(f"Unrecognized rule {rule} in exp {scoped_name_exp(e)}")        

    return result


def scoped_name_statement(s,scoped_name_env):
    rule = node_rule(s, "statement")
    result = deepcopy(s)
    match(rule):
        case ['lval', 'EQ', _]: # Assignment
            [lval,EQ,exp]    = s.children
            lval0 = scoped_name_lval(lval,scoped_name_env)
            exp0  = scoped_name_exp (exp, scoped_name_env)
            result.children = [lval0,EQ,exp0]
                
        case ['qupdate']:
            [qupdate] = s.children
            qupdate0 = scoped_name_qupdate(qupdate,scoped_name_env)
            result.children = [qupdate0]
        
        case ['qupdate','IF',_]:  # Quantum update
            (qupdate,IF,lval) = s.children
            qupdate0  = scoped_name_qupdate(qupdate,scoped_name_env)
            lval0     = scoped_name_lval   (lval,   scoped_name_env) 
            result.children = [qupdate0,IF,lval0]            

        case ['MEASURE',_,_]: # qbit measurement
            [MEASURE,qbit,cbit]   = s.children
            qbit0 = scoped_name_lval(qbit,scoped_name_env) # measure changes both
            cbit0 = scoped_name_lval(cbit,scoped_name_env) # cbit and qbit
            result.children = [MEASURE,qbit0,cbit0]

        case ['IF', _, 'statement', 'statement']:
            [IF,exp,stat_true, stat_false] = s.children
            exp0             = scoped_name_exp(exp,scoped_name_env)
            true0  = scoped_name_statement(stat_true,scoped_name_env)
            false0 = scoped_name_statement(stat_false,scoped_name_env)
            result.children = [IF,exp0,true0,false0]

        case ['WHILE', _, 'statement']:
            [WHILE,exp_test, stat] = s.children
            exp0   = scoped_name_exp(exp_test,  scoped_name_env)
            stat0  = scoped_name_statement(stat,scoped_name_env)
            result.children = [WHILE,exp0,stat0]
        
        case ['block']:
            [block] = s.children
            decls, stats = block.children
            
            block_scope = new_scope(scoped_name_env)
            block_env   = scoped_name_env + [block_scope]

            # This changes block_scope
            decls0 = [scoped_name_declaration(d,block_env) for d in decls.children]
            #print(f"Block scope after declarations: {block_scope}")
            stats0 = [scoped_name_statement(c,block_env) for c in stats.children]
            
            result = make_block(decls0, stats0)

    return result



def scoped_name_declaration(d,scoped_name_env):
    # vars_declaration both computes which variables are read and written
    # and updates the environment with the new variable declarations
    rule = node_rule(d, "declaration")
    (name,type) = typeof_declaration(d)

    result = deepcopy(d)
    match(rule):
        case ['TYPE','lval']: # Scalar variable declaration
            [TYPE,lval] = d.children
            # First add the variable to the current scope, so it will resolve correctly
            scope = scoped_name_env[-1]
            scope[name] = (type,scope['?scope_id'])
            # Then look up the lval base, and variables referenced in its index expression
            lval0 = scoped_name_lval(lval,scoped_name_env)
            result.children = [TYPE,lval0]

        case ['TYPE','ID',_]: # Scalar variable with initial value
            [TYPE,lval,exp] = d.children
            # First add the variable to the current scope, so it will resolve correctly
            scope = scoped_name_env[-1]
            scope[name] = (type,scope['?scope_id'])
            # Then look up the lval base, and variables referenced in its index expression
            lval0 = scoped_name_lval(lval,scoped_name_env)
            exp0  = scoped_name_exp(exp,scoped_name_env)
            result.children = [TYPE,lval0,exp0]
        
        case ['TYPE','ID',_,'exps']: # Array variable with initial values
            [TYPE,lval,e_size,exps] = d.children
            # First add the variable to the current scope, so it will resolve correctly
            scope = scoped_name_env[-1]
            scope[name] = (type,scope['?scope_id'])
            # Then look up the lval base, and variables referenced in its index expression
            lval0   = scoped_name_lval(lval,scoped_name_env)
            e_size0 = scoped_name_exp(e_size,scoped_name_env)
            # ...and the variables referenced in the initialization expressions
            exps0 = [scoped_name_exp(e,scoped_name_env) for e in exps.children]
            result.children[:3] = [TYPE,lval0,e_size0]
            result.children[3].children = exps0

    return result

def scoped_name_qupdate(qupdate,scoped_name_env):
    rule = node_rule(qupdate, "qupdate")
    # A quantum update reads from the index expressions
    # and writes to the qbit variables.
    result = deepcopy(qupdate)
    match(rule):
        case ['gate', 'lval']:
            [gate,lval] = qupdate.children
            lval0 = scoped_name_lval(lval,scoped_name_env)
            result.children = [gate,lval0]

        case ['lval','SWAP','lval']: 
            [lval1,SWAP,lval2] = qupdate.children
            l1 = scoped_name_lval(lval1,scoped_name_env)
            l2 = scoped_name_lval(lval2,scoped_name_env)
            result.children = [l1,SWAP,l2]

    return result


