from copy import deepcopy
from lark.tree import Tree
from lark.lexer import Token

from helpers import *
from show import *
from showcq import *
from type import *
# We recurse through the abstract syntax tree using a set of mutually recursive functions,
# one for each node type in the AST (corresponding to rules in the grammar):
# exp(e,env):
# procedure(p,env):
# parameter_declaration(d,env): 
# declaration(d,env):
# lval(v,env):
# qupdate(q,env):
# gate(g,env):
# statement(s,env):


# Online partial evaluation of a CQ-program. 
# The static subset of the main procedure's parameters are given as a start environment, `static_input`.
# See in helpers.py for how make_program, make_block, etc. build Lark AST nodes.

# Input:
# - P:            A parse tree AST for a full CQ program
# - static_input: A single dict on the form {'variable-name': value,...}  with the static input values.
# Returns:
#   The residual program AST after partial evaluation
def PE_program(P, static_input):
    procedures = P.children

    function_table = {}

    for p in procedures:
        fname, params, stat = p.children
        function_table[f"{fname}"] = (params, stat)

    main = procedures[0]
    main_params = type_procedure_parameters(main, [{}])

    # When partial evaluation is done, we should only have a single procedure left, the main procedure.
    residual_main  = PE_procedure(main,[function_table,static_input])
    return make_program([residual_main])

# Partial evaluation of a CQ-procedure:
# Input:
# - p:         a CQ procedure AST subtree
# - value_env: a list of dict's denoting scopes, the last element in the list being the current scope (corresponding to the top of the stack)
# Returns:
#  The residual procedure AST after partial evaluation
def PE_procedure(p,value_env):
    [name,param_decls,stat] = p.children

    name, params = type_procedure_parameters(p,[{}])    
    
    # For symbolic array sizes in static arrays, the symbolic size is known and should be bound.
    # (e.g. `float A[N]` binds N to the length of A).
    sizes  = [(n,array_size(t)) for (n,t) in params]
    
    procedure_scope = {}
    for (a,s) in sizes:
        value = lookup_lval(a,value_env)
        if (    (value is not None)  # This is a static parameter
            and (s is not None)                         # which is an array
            and (not s.isnumeric())):                   # With symbolic size
            
            procedure_scope[s] = len(value)

    (residual_statement,fully_evaluated) = PE_statement(stat, value_env+[procedure_scope])
    residual_params    = [PE_parameter_declaration(d,value_env) for d in param_decls.children]
    residual_params    = [d for (d,static) in residual_params if not static] # Filter out fully evaluated declarations

    return make_procedure(name,residual_params,residual_statement)        

# Partial evaluation of a parameter_declaration:
# Input:
# - p:         a CQ parameter_declaration subtree
# - value_env: a list of dict's denoting scopes, the last element in the list being the current scope (corresponding to the top of the stack)
# Returns a pair (d',sigma), where:
#  - d' is the residual parameter_declaration AST, and
#  - sigma is a bool denoting whether it is fully static or contains dynamic parts.    
def PE_parameter_declaration(d,value_env):
    rule = node_rule(d, "parameter_declaration")
    #print(f"type_parameter_declaration: {rule} in {show_parameter_declaration(d)}")
    result = deepcopy(d)
    match(rule):
        case ['TYPE','ID']:        # Scalar declaration
            type, name = d.children
            is_static  = lookup_scope(name,value_env) != -1
            return (result, is_static)  
        case ['TYPE','ID','INT']:  # Constant size array 
            type, name, size = d.children
            is_static        = lookup_scope(name,value_env) != -1            
            return (result, is_static)  
        case ['TYPE','ID','ID']:   # Variable size array
            type, name, size = d.children
            vsize            = lookup_lval(size,value_env)
            is_static        = lookup_scope(name,value_env) != -1            
            
            if vsize is not None: # The size is statically known
                result.children[2] = Token('INT', vsize)
                return (result, is_static)  
            else:
                return (result, False)
        case _: 
            raise Exception(f"Unrecognized rule {rule} in parameter_declaration {d}")

    

# Partial evaluation of a lvals:
#
# NB: We use lvals in three different ways:
# 1. In a declaration, in which a[exp] is a declaration of an array of size exp
# 2. In an assignment, in which a[exp] is an assignment to the exp-th element of a
# 3. In an expression, in which a[exp] is an expression that evaluates to the exp-th element of a
# However, since we use a single grammar rule for all three and one function to process them, we need to be a little careful. 
#
# Use PE_lval in the following way for the 3 cases:
# 1. (reduced lval, size, fully_resolved?)
# 2. (reduced lval, index, fully_resolved?)
# 3. (reduced lval, index, fully_resolved?), lookup value subsequently
#
# Input:
# - v:         a CQ lval subtree
# - value_env: a list of dict's denoting scopes
# Returns a tuple consisting of
#   - the residual AST after partial evaluation
#   - the lval base name      (e.g. 'a' for 'a[23+b]')
#   - the residual size/index (e.g. the AST for 23+b for 'a[23+b]' if b is dynamic, or 25 if b=2 at time of evaluation.
#   - a boolean denoting whether the lval was fully resolved to a concrete memory address that can be written to or read from.
def PE_lval(v,env):
    rule = node_rule(v, "lval")

    result = deepcopy(v)
    try:
        match(rule):
            case ['ID']:       
                [name] = v.children
                return (result, name,None, True)
            case ['ID','INT']: 
                [name,size_or_index] = v.children
                return (result, name,int(size_or_index), True)
            case ['ID',_]: 
                [name,exp]    = v.children
                #print(f"PE_lval: {name}[{showcq_exp(exp)}]")
                (size_or_index,static) = PE_exp(exp,env)
                result.children[1] = size_or_index

                #print(f"exp -> {size_or_index}")
                if static:
                    #print(f"resolved: {(name,size_or_index,True)}")
                    return (result,name,size_or_index, True)
                else:
                    #print(f"unresolved: {(result,None,False)}")
                    return (result, name, None, False)
            case _: 
                raise Exception(f"Unrecognized rule {rule} in lval-node {showcq_lval(v)}")
    except:
        raise Exception(f"Error evaluating rule {rule} for lval-node {showcq_lval(v)}")
                
    
# Partial evaluation of declaration.
# Input:
# - d:         a CQ declaration subtree
# - value_env: a list of dict's denoting variable scopes.
# Returns a pair (d',sigma), where:
#  - d' is the residual declaration AST after partial evaluation
#  - sigma is a bool denoting whether it is fully static or contains dynamic parts.    
def PE_declaration(d,value_env):
    # 1. Scalar declarations without initializations initialize the lval to 0
    # 2. Array declarations without initializations initialize the lval to an array of zeros
    #    of the declared size
    # 
    # 3.+4.: Declarations with initializations are handled as follows: 
    # The RHS expressions are evaluated. If they are static, the lval is initialized to the
    # static value. If the RHS is not static, the lval is dynamic, and 
    # the declaration is specialized to the residual expression.

    rule = node_rule(d, "declaration")
    result = deepcopy(d)
    #print(f"PE_declaration: {rule} for {showcq_declaration(d)}\n in env = {env[1:]}")
    match(rule):
      #####################################################
      ########### YOUR IMPLEMENTATION GOES HERE ###########     
      #####################################################            
        case _:
            raise Exception(f"Unrecognized rule {rule} in declaration-node {showcq_declaration(d)}")
    
    raise Exception(f"Unrecognized rule {rule} in declaration-node {showcq_declaration(d)}")

# Partial evaluation of statements.
# Input:
# - s:         a CQ statement subtree
# - value_env: a list of dict's denoting scopes.
# Returns (s',sigma), where:
#  - s' is the residual statement AST after partial evaluation, and
#  - sigma is True iff s was fully static (and thus fully evaluated away, i.e. s' = {} = skip) 
def PE_statement(s,value_env):
    rule = node_rule(s, "statement")
    #print(f"PE_statement: {rule}: {showcq_statement(s)}\nin env = {value_env[1:]}")
    result = deepcopy(s)    
    skip   = make_skip_statement()
    try:
        match(rule):
      #####################################################
      ########### YOUR IMPLEMENTATION GOES HERE ###########     
      #####################################################            
            case _:
                raise Exception(f"Unrecognized rule {rule} in statement-node {showcq_statement(s)}")
    except:
        raise Exception(f"Error evaluating rule {rule} for statement-node {showcq_statement(s)}")            

# Partial evaluation of qupdate
# Input:
# - q:         a CQ qupdate subtree
# - value_env: a list of dict's denoting scopes.
# Returns q', where:
#  - q' is the residual AST after partial evaluation
# Since qupdates are never fully static, we don't return a sigma
def PE_qupdate(q,env):
    rule = node_rule(q, "qupdate")
    #print(f"PE_qupdate: {rule}: {showcq_qupdate(q)}")
    result = deepcopy(q)
    try:
        match(rule):
            case ['gate','lval']:
                [gate,lval] = q.children
                (g,_) = PE_gate(gate, env)
                (l,_,_,_) = PE_lval(lval, env)
                result.children = [g,l]
                #print(f"Replacing {showcq_qupdate(q)} with {showcq_qupdate(result)} (env={env})")
                return result
            case ['lval', 'SWAP', 'lval']:
                [lval1,SWAP,lval2] = q.children
                (l1,_,_,_) = PE_lval(lval1, env)
                (l2,_,_,_) = PE_lval(lval2, env)
                result.children = [l1,SWAP,l2]
                #print(f"Replacing {showcq_qupdate(q)} with {showcq_qupdate(result)}")                
                return result
            case _:
                raise Exception(f"Unrecognized rule {rule} in qupdate-node {showcq_qupdate(q)}")
    except:
        raise Exception(f"Error evaluating rule {rule} for qupdate-node {showcq_qupdate(q)}")        

# Partial evaluation of gate
# Input:
# - g:         a CQ gate subtree
# - value_env: a list of dict's denoting scopes.
# Returns g', where:
#  - g' is the residual AST after partial evaluation                
def PE_gate(g,env):
    rule = node_rule(g, "gate")
    #print(f"PE_gate: {rule}: {showcq_gate(g)}")
    result = deepcopy(g)
    try:
        match(rule):
            case ['NOT'] | ['H']: 
                return (g,True)
            case ['rgate',_]:
                [rgate, angle_exp] = g.children
                (a,a_static)       = PE_exp(angle_exp, env)
                result.children    = [rgate,a]
                return (result, a_static)
            case _:
                raise Exception(f"Unrecognized rule {rule} in gate-node {showcq_gate(g)}")
    except:
        raise Exception(f"Error evaluating rule {rule} for gate-node {showcq_gate(g)}")

# Partial evaluation of expressions
# Input:
# - e:         a CQ exp subtree
# - value_env: a list of dict's denoting scopes.
# Returns (e',sigma) where:
#  - e' is a numerical value of the expression's type, if the expression is fully static, or the residual AST if it contained dynamic parts, and 
#  - sigma specifies whether e was fully static, i.e., whether e' is just a number.
def PE_exp(e,value_env):
    # Is this a terminal (a leaf node), or does e have children?
    match(node_name(e)):
        case 'NUMERICAL_VALUE': return (e,True)        
        case 'INT' | 'FLOAT':   return (literal_eval(e.value), True)
        case 'NAMED_CONSTANT':  return (named_constants[e.value],True)

    # e has children to process.
    rule = node_rule(e, "exp")
    #print(f"PE_exp: {rule}: {showcq_exp(e)} with env={env}")
    result = deepcopy(e)
    try:
        match(rule):
            case ['UNOP', _]:       # Unary operation
                unop, e1 = e.children
                (v1,v1_static) = PE_exp(e1,value_env)
                if v1_static:
                    return (evaluate_unop[unop](v1), True)
                else:
                    result.children[1] = v1
                    return (result,False)
        
            case [_,'BINOP',_] | [_,'PE',_] | [_,'MD',_] | [_,'AS',_] | [_,'CMP',_]: 
                e1,binop,e2 = e.children
                (v1,v1_static) = PE_exp(e1,value_env)
                (v2,v2_static) = PE_exp(e2,value_env)

                if v1_static and v2_static:
                    return (evaluate_binop[binop](v1,v2), True)
                else:
                    result.children[0] = v1
                    result.children[2] = v2
                    return (result,False)

            case ['BUILTIN_FUN1', _]:
                fun, e1 = e.children
                (v1,v1_static) = PE_exp(e1,value_env)
                
                if v1_static:
                    return (evaluate_fun[fun](v1),True)
                else:
                    result.children[1] = v1                
                    return (result,False)
            
            case ['BUILTIN_FUN2', _, _]:
                fun, e1, e2 = e.children
                (v1,v1_static) = PE_exp(e1,value_env)
                (v2,v2_static) = PE_exp(e2,value_env)

                if v1_static and v2_static:
                    return (evaluate_fun[fun](v1,v2),True)
                else:
                    result.children[1] = v1
                    result.children[2] = v2
                    return (result,False)
            
            case ['ID']: 
                [var] = e.children
                v = lookup_lval(var,value_env)
                if v is not None:
                    return (v,True)
                else:
                    return (result,False)

            case ['ID', _]:
                [var,e1] = e.children
                (index,index_static) = PE_exp(e1,value_env)
                vs                   = lookup_lval(var,value_env)
                
                if vs is not None and index_static:
                    return (vs[index],True)
                else:
                    result.children[1] = index
                    return (result,True)        
          case _:
            raise  Exception(f"evaluate_exp: {rule} not implemented")        
    except:        
        raise Exception(f"Error evaluating exp-node with rule {rule} for node {showcq_exp(result)}") 




