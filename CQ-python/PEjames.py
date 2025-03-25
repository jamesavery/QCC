from copy import deepcopy
from lark.tree import Tree
from lark.lexer import Token

from helpers import *
from show import *
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
            raise Exception(f"PE_parameter_declaration: Unrecognized rule {rule} in {show_parameter_declaration(d)}")

# Full evaluation/interpretation of classical expression
# Solution to assignment 1.5
def evaluate_lval(id, index_exp, env): 
    name  = f"{id}"
    scope = lookup_scope(name, env)
    
    try:
        if(index_exp is None):
            return env[scope][name]
        else:
            n_index = evaluate_exp(index_exp, env)
            return env[scope][name][n_index]
    except Exception as e:
        print(f"evaluate_lval encountered error {e} evaluating lval {name}[{index_exp}] in scope {scope} in environment {env}")
        raise e


def evaluate_exp(e, env):
    # match(node_name(e)):
    #     case 'NUMERICAL_VALUE': return e        
    #     case 'INT' | 'FLOAT':  return literal_eval(e.value)
    #     case 'NAMED_CONSTANT': return named_constants[e.value]    
        
    if isinstance(e, Token):
        print(f"evaluate_exp encountered token {e}")
        assert(False)   

    # e has children to process.
    rule  = [node_name(c) for c in e.children]

    match(rule):
        case ['exp']:
            [e1] = e.children
            return evaluate_exp(e1,env)
        case ['INT'] | ['FLOAT']:
            [c] = e.children
            return literal_eval(c.value)
        case ['NAMED_CONSTANT']:
            [c] = e.children
            return named_constants[c.value]
        case ['lval']:
            [lv] = e.children
            (lv0, name, index, static) = PE_lval(lv, env)
            if static:
                return evaluate_lval(name, index, env)
            else:
                raise Exception(f"evaluate_exp: unresolved lval {show_lval(lv)}")
        
        case ['UNOP', 'exp']:       # Unary operation
            unop, e1 = e.children
            v1 = evaluate_exp(e1,env)
            return evaluate_unop[unop](v1);            
        
        case ['exp','BINOP','exp']:
            e1,binop,e2 = e.children
            v1,v2 = evaluate_exp(e1,env), evaluate_exp(e2,env)
            v3 = evaluate_binop[binop](v1,v2)            
            return v3

        case ['BUILTIN_FUN1', 'exp']:
            fun, e1 = e.children
            v1 = evaluate_exp(e1,env)
            v2 = evaluate_fun[fun](v1) 
            return v2
        
        case ['BUILTIN_FUN2', 'exp', 'exp']:
            fun, e1, e2 = e.children
            v1, v2 = evaluate_exp(e1), evaluate_exp(e2,env)
            return evaluate_fun[fun]()
        
    raise Exception(f"evaluate_exp: {rule} not implemented")

    

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
#   - the residual size/index as an expression AST 
#     (e.g. the AST for 23+b for 'a[23+b]' if b is dynamic, or AST for 25 (exp->INT(25)) if b=2 at time of evaluation.
#   - a boolean denoting whether the lval was fully resolved to a concrete memory address that can be written to or read from.
def PE_lval(v,env):
    rule = node_rule(v, "lval")

    result = deepcopy(v)
    try:
        id = v.children[0]
        name = f"{id}"
        match(rule):
            case ['ID']:       
                scope = lookup_scope(name,env)
                static = scope != -1
                if static:
                    return (result, name, None, True)
                else:
                    return (result, name,None, False)
            case ['ID','INT']: 
                [_,size_or_index] = v.children
                return (result, name,make_constant(size_or_index.value), True)
            case ['ID','exp']: 
                [_,exp]    = v.children
                #print(f"PE_lval: {name}[{show_exp(exp)}]")
                (size_or_index,static_index) = PE_exp(exp,env)
                result = make_lval(name,size_or_index)

                scope  = lookup_scope(name,env)
                static = scope != -1

                if static and static_index:
                    #print(f"resolved: {(name,size_or_index,True)}")
                    return (result,name,size_or_index, True)
                else:
                    #print(f"unresolved: {(result,None,False)}")
                    return (result, name, size_or_index, False)
            case _: 
                raise Exception(f"PE_lval: Unrecognized rule {rule} in lval-node {show_lval(v)}")
    except:
        raise Exception(f"PE_lval: Error evaluating rule {rule} for lval-node {show_lval(v)}")
                
    
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
    #print(f"PE_declaration: {rule} for {show_declaration(d)}\n in env = {env[1:]}")
    match(rule):
        case ['TYPE','lval']: # Zero initialization
            [type,lval] = d.children
            (lval0, name,size,is_resolved) = PE_lval(lval, value_env) 
            result.children[1] = lval0

            # Can we perform the actual initialization?
            if is_resolved: # Do we know the address of the lval?
                # Update value in current scope
                if size is None:
                    value_env[-1][name] = 0
                else:
                    n_size = evaluate_exp(size,value_env)
                    value_env[-1][name] = [0]*n_size
                #print(f"initialized {l}, env = {env}")
                return (result,True)
            else:
                return (result,False)
            
        case ['TYPE','ID','exp']: # Scalar initialization; lval always resolved.
            [type,id,exp] = d.children
            name = f"{id}"
            (v,v_static) = PE_exp(exp,value_env) 
            result.children[2] = v            

            if v_static:
                scope = lookup_scope(name, value_env) # In which scope is l defined?
                n     = evaluate_exp(v,value_env)
                value_env[scope][name] = n
                return (result,True)
            else:
                return (result,False)

        case ['TYPE','ID','INT','exps']: # Array declaration with initialization 
            [type,id,size,exps] = d.children
            name = f"{id}"
            values               = [PE_exp(e,value_env) for e in exps.children]

            result.children[2] = make_constant(size.value)
            result.children[3].children = [v for (v,static) in values]

            if(size.value == len(values)):
                print(f"Array {name} of size {size.value} initialized with {len(values)} values: {values}")
                assert(False)

            if all([static for (v,static) in values]):
                scope = lookup_scope(name, value_env) # In which scope is l defined?
                ns = [evaluate_exp(v,value_env) for (v,static) in values]
                value_env[scope][name] = ns
                return (result,True)
            else:
                return (result,False)
        case _:
            raise Exception(f"PE_declaration: Unrecognized rule {rule} in {show_declaration(d)}")
    
    

# Partial evaluation of statements.
# Input:
# - s:         a CQ statement subtree
# - value_env: a list of dict's denoting scopes.
# Returns (s',sigma), where:
#  - s' is the residual statement AST after partial evaluation, and
#  - sigma is True iff s was fully static (and thus fully evaluated away, i.e. s' = {} = skip) 
def PE_statement(s,value_env):
    rule = node_rule(s, "statement")
    #print(f"PE_statement: {rule}: {show_statement(s)}\nin env = {value_env[1:]}")
    result = deepcopy(s)    
    skip   = make_skip_statement()
    try:
        match(rule):
            case ['lval', 'EQ', 'exp']: # Assignment
                [lval,EQ,exp]    = s.children
                #print(f"['lval', 'EQ', _]: {show_lval(lval)} = {show_exp(exp)}")                    
                (lval0,name,index,lhs_static) = PE_lval(lval, value_env)
                #print(f"lval = {lv}, index = {index}, lval_resolved = {lval_resolved}")
                (rhs,rhs_static) = PE_exp(exp,value_env)
                if lhs_static and rhs_static:
                    scope = lookup_scope(name, value_env) # In which scope is l defined?
                    ns    = evaluate_exp(rhs,value_env)
                    if index is None:
                        value_env[scope][name] = ns
                    else:
                        n_index = evaluate_exp(index,value_env)
                        value_env[scope][name][n_index] = ns
                    #print(f"resolved assignment, env = {value_env}")  
                    return (skip,True)
                else:
                    #print(f"unresolved assignment, {show_lval(lv)} = {show_exp(rhs)}")
                    result.children = [lval0,EQ,rhs]
                    return (result,False)
                
            case ['IF', 'exp', 'statement', 'statement']:
                [IF, cond, s1, s2] = s.children
                (c,c_static) = PE_exp(cond, value_env)
                #print(f"IF: {c}")
                if c_static:
                    #print(f"IF: {c} is statically determined")
                    if evaluate_exp(c, value_env):
                        return PE_statement(s1, value_env)
                    else:
                        return PE_statement(s2, value_env)
                else:
                    #print(f"IF: {c} is not static. DON'T PE STATEMENTS, AS THIS WILL CHANGE STATE")
                    # TODO: Copy the environment, and apply the side-effects to the copy. 
                    #       Then replace statements by blocks that apply side-effects as assignments.
                    #value_env_copy = deepcopy(value_env)
                    #s1 = PE_statement(s1, value_env_copy)
                    #s2 = PE_statement(s2, value_env_copy)
                    #diff1 = {k: value_env_copy[k] for k in value_env_copy if k not in value_env}
                    #diff2 = {k: value_env[k] for k in value_env if k not in value_env_copy}
                    #side_effects1 = [make_assignment(k, diff1[k]) for k in diff1]
                    #side_effects2 = [make_assignment(k, diff2[k]) for k in diff2]
                    #S1p = make_block([s1]+side_effects1)
                    #S2p = make_block([s2]+side_effects2)
                    #return (make_if(c,S1p,S2p), False)
                    result.children = [IF, c, s1, s2]
                    return (result,False)
            
            case ['WHILE', 'exp', 'statement']:
                [WHILE, cond, s1] = s.children
                #print(f"WHILE: {show_exp(cond)} {show_statement(s1)}")
                (c,c_static) = PE_exp(cond, value_env)

                # If c is static, c will keep being static, and we can fully unroll the loop                
                # (we do not currently worry about non-termination)
                if c_static: 
                    residual_statements = []
                    while evaluate_exp(c, value_env):
                        residual_statements += [PE_statement(s1, value_env)]
                        (c,_) = PE_exp(cond, value_env)
                    
                    # TODO: Copy the environment, and apply side effects to the copy. Append statements that apply side-effects as assignments.
                    residual_statements = [s for (s,static) in residual_statements if not static]
                    if residual_statements == []:
                        return (skip,True)
                    else:
                        return (make_block([],residual_statements), False)
                else:
                    # value_env_copy = deepcopy(value_env)
                    # S1 = PE_statement(s1, value_env_copy)
                    # diff = {k: value_env_copy[k] for k in value_env_copy if k not in value_env}
                    # side_effects = [make_assignment(k, diff[k]) for k in diff]
                    # Sp = make_block([S1]+side_effects)
                    # return (make_while(c,Sp), False)
                    result.children = [WHILE, c, s1]
                    return (result,False)            
                
            case ['block']:
                [block] = s.children
                decls, stats = block.children

                #print(f"['block']:\n\t{decls}\n\t{stats}")

                residual_declarations = []
                residual_statements   = []

                # A new environment scope is created for the block as follows:
                new_scope = {}
                for d in decls.children:
                    residual_declarations += [PE_declaration(d,value_env+[new_scope])]
                #print(f"block scope = {new_scope}")

                for s in stats.children:
                    residual_statements += [PE_statement(s, value_env+[new_scope])]
                
                residual_declarations = [d for (d,static) in residual_declarations if not static]
                residual_statements   = [s for (s,static) in residual_statements   if not static]

                return (make_block(residual_declarations,residual_statements), False)
                
            case ['qupdate']:
                [qupdate] = s.children
                q = PE_qupdate(qupdate, value_env)
                result.children = [q]
                return (result,False)
            
            case ['qupdate','IF','lval']:
                [qupdate,IF,lval] = s.children
                Q = PE_qupdate(qupdate, value_env)
                (qbit,_,_,_) = PE_lval(lval, value_env)                
                result.children = [Q,IF,qbit]
                return (result,False)
            
            case ['MEASURE','lval','lval']:
                [MEASURE,qbit,cbit] = s.children
                (q,_,_,_) = PE_lval(qbit, value_env)
                (c,_,_,_) = PE_lval(cbit, value_env)
                result.children = [MEASURE,q,c]
                return (result,False)
            
            case ['procedure_call']:
                return (result,False) # Partial evaluation of procedure calls is not implemented yet
            
            case _:
                raise Exception(f"PE_statement: Unrecognized rule {rule} in {show_statement(s)}")
    except Exception as e:
        print(f"PE_statement: {e} when evaluating {rule} in {s.pretty()}")
        raise e

# Partial evaluation of qupdate
# Input:
# - q:         a CQ qupdate subtree
# - value_env: a list of dict's denoting scopes.
# Returns q', where:
#  - q' is the residual AST after partial evaluation
# Since qupdates are never fully static, we don't return a sigma
def PE_qupdate(q,env):
    rule = node_rule(q, "qupdate")
    #print(f"PE_qupdate: {rule}: {show_qupdate(q)}")
    result = deepcopy(q)
    try:
        match(rule):
            case ['gate','lval']:
                [gate,lval] = q.children
                g = PE_gate(gate, env)
                (l,_,_,_) = PE_lval(lval, env)
                result.children = [g,l]
                #print(f"Replacing {show_qupdate(q)} with {show_qupdate(result)} (env={env})")
                return result
            case ['lval', 'SWAP', 'lval']:
                [lval1,SWAP,lval2] = q.children
                (l1,_,_,_) = PE_lval(lval1, env)
                (l2,_,_,_) = PE_lval(lval2, env)
                result.children = [l1,SWAP,l2]
                #print(f"Replacing {show_qupdate(q)} with {show_qupdate(result)}")                
                return result
            case _:
                raise Exception(f"PE_qupdate: Unrecognized rule {rule} in {show_qupdate(q)}")
    except Exception as e:
        print(f"PE_qupdate: {e} when evaluating {rule} in {q.pretty()}")
        raise e
        

# Partial evaluation of gate
# Input:
# - g:         a CQ gate subtree
# - value_env: a list of dict's denoting scopes.
# Returns g', where:
#  - g' is the residual AST after partial evaluation                
def PE_gate(g,env):
    rule = node_rule(g, "gate")
    #print(f"PE_gate: {rule}: {show_gate(g)}")
    result = deepcopy(g)
    try:
        match(rule):
            case ['NOT'] | ['H']: 
                return g
            case ['rgate','exp']:
                [rgate, angle_exp] = g.children
                (a,a_static)       = PE_exp(angle_exp, env)
                result.children    = [rgate,a]
                return result
            case _:
                raise Exception(f"PE_gate Unrecognized rule {rule} in {show_gate(g)}")
    except Exception as e:
        print(f"PE_gate: {e} when evaluating {rule} in {g.pretty()}")
        raise e
    

# Partial evaluation of expressions
# Input:
# - e:         a CQ exp subtree
# - value_env: a list of dict's denoting scopes.
# Returns (e',sigma) where:
#  - e' is a numerical value of the expression's type, if the expression is fully static, or the residual AST if it contained dynamic parts, and 
#  - sigma specifies whether e was fully static, i.e., whether e' is just a number.
def PE_exp(e,value_env):
    assert(isinstance(e, Tree) and e.data == "exp")
    
    rule = node_rule(e, "exp")
    #print(f"PE_exp: {rule}: {show_exp(e)} with env={env}")
    result = deepcopy(e)
    try:
        match(rule):
            case ['exp']:
                [e1] = e.children
                return PE_exp(e1,value_env)

            case ['INT'] | ['FLOAT']:
                [c] = e.children
                n   = literal_eval(c.value)
                return (make_constant(n),True)
            
            case ['NAMED_CONSTANT']:
                [c] = e.children
                n   = named_constants[c.value]
                return (make_constant(n),True)
                
            case ['UNOP', 'exp']:       # Unary operation
                unop, e1 = e.children
                (v1,v1_static) = PE_exp(e1,value_env)
                if v1_static:
                    n1 = evaluate_exp(v1,value_env)
                    n  = evaluate_unop[unop](n1)
                    return (make_constant(n),True)
                else:
                    result.children[1] = v1
                    return (result,False)
        
            case ['exp','BINOP','exp']: 
                e1,binop,e2 = e.children
                (v1,v1_static) = PE_exp(e1,value_env)
                (v2,v2_static) = PE_exp(e2,value_env)

                if v1_static and v2_static:
                    n1 = evaluate_exp(v1,value_env)
                    n2 = evaluate_exp(v2,value_env)
                    n      = evaluate_binop[binop](n1,n2)
                    return (make_constant(n),True)
                else:
                    result.children[0] = v1
                    result.children[2] = v2
                    return (result,False)

            case ['BUILTIN_FUN1', 'exp']:
                fun, e1 = e.children
                (v1,v1_static) = PE_exp(e1,value_env)
                
                if v1_static:
                    n1 = evaluate_exp(v1,value_env)
                    n  = evaluate_fun[fun](n1)
                    return (make_constant(n),True)
                else:
                    result.children[1] = v1                
                    return (result,False)
            
            case ['BUILTIN_FUN2', 'exp', 'exp']:
                fun, e1, e2 = e.children
                (v1,v1_static) = PE_exp(e1,value_env)
                (v2,v2_static) = PE_exp(e2,value_env)

                if v1_static and v2_static:
                    n1, n2 = evaluate_exp(v1,value_env), evaluate_exp(v2,value_env)
                    n      = evaluate_fun[fun](n1,n2)
                    return (make_constant(n),True)
                else:
                    result.children[1] = v1
                    result.children[2] = v2
                    return (result,False)
            
            case ['lval']:
                [lv] = e.children
                (lval0,name, index, static) = PE_lval(lv,value_env)
                if static:
                    n = evaluate_lval(name,index,value_env)                    
                    return (make_constant(n),True)
                else:
                    return (make_exp([lval0]),False)
            case _:
                raise Exception(f"PE_exp: Unrecognized rule {rule} in {show_exp(e)}")

    except Exception as ex:
        print(f"PE_exp: {ex} when evaluating {rule} in {e}")
        raise ex

