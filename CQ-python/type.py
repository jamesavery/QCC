from show import *
from show import *
from helpers import *
from ast import literal_eval

# type_procedure(p,type_env)
# type_statement(s,type_env)
# type_lval(l,type_env)
# type_declaration(d,type_env)
# type_parameter_declaration(d,type_env)
# type_exp(e,type_env)
# type_qupdate(q,type_env)
def type_program(p):
    procedures = p.children
    
    function_table = {}

    # Build procedure table
    #print(f"Procedures: {procedures}")
    for p in procedures:
        name, params = type_procedure_parameters(p,[])
        if name in function_table:
            raise NameError(f"Duplicate procedure name {name}")
        
        function_table[name] = params

    for p in procedures:
        name, params = type_procedure_parameters(p,[])
        if(type_procedure(p, [function_table])):
            print(f"Procedure {name} is well-typed")
        else: 
            print(f"Procedure {name} is not well-typed")
    
    return True

def type_procedure_parameters(p,type_env):

    [name,param_decls,stat] = p.children
    # Parameter types: list of (name, type) pairs.
    params = [type_parameter_declaration(d,type_env) for d in param_decls.children]

    return (name, params)

def type_parameter_declaration(d,type_env):
    rule = node_rule(d, "parameter_declaration")
    #print(f"type_parameter_declaration: {rule} in {show_parameter_declaration(d)}")
    match(rule):
        case ['TYPE','ID']:        # Scalar declaration
            type, name = d.children
            return (f"{name}", f"{type}")
        
        case ['TYPE','ID','INT']:  # Constant size array 
            type, name, size = d.children
            return (f"{name}", f"{type}[{size}]")
        
        case ['TYPE','ID','ID']:   # Variable size array
            type, name, size = d.children
            return (f"{name}", f"{type}[{size}]")
                    
        case _: 
            raise Exception(f"Unrecognized rule {rule} in parameter_declaration {d}")


def type_lval(l,type_env):
    rule = node_rule(l, "lval")
    match(rule):
        case ['ID']: 
            [name] = l.children
            type = lookup_lval(name, type_env)
            size = array_size(type)
           # NB:lvals in procedure calls refer to the array by base name, not including size.

        case ['ID', 'exp']: # id[exp]
            [name,exp_index] = l.children
            t1 = lookup_lval(name, type_env)
            t2 = type_exp(exp_index,type_env)
            if t1 is None:
                raise NameError(f"Variable {name} referenced before definition (type_env={type_env})")
            if t2 != 'int':
                raise TypeError(f"Array index {show_exp(exp_index)} of {name} must be of type int (got {t2})")
            size = array_size(t1)
            if size is None:
                raise TypeError(f"Variable {name} is accessed as an array, but is typed as {t1}")
            type = array_base(t1)

        case _: 
            raise Exception(f"Unrecognized rule {rule} in lval {l}")
    if type is None:
        raise NameError(f"Variable {l} referenced before definition")
    return type

def type_procedure(p,type_env):
    [name,param_decls,stat] = p.children
    [function_table] = type_env

    params = function_table[name]        
    # Symbolic array sizes (e.g. `float A[N]` should add `int N` to the type environment.)    
    sizes  = [(n,array_size(t)) for (n,t) in params]

    #print(f"sizes = {sizes}")
    procedure_scope = dict(params)
    for (n,s) in sizes:
        if s is not None and not s.isnumeric(): # Symbolic size
            if s in procedure_scope:
                 raise NameError(f"Symbolic size {s} name clash with parameter of type {procedure_scope[s]}")
        procedure_scope[s] = 'int'
            
    return type_statement(stat,type_env+[procedure_scope])

# Statement type checker returns true if the statement is well-typed, and raises an exception otherwise.
def type_statement(s,type_env):

    rule = node_rule(s, "statement")
    #print(f"type_statement: {rule} in {show_statement(s)}")
    match(rule):
        case ['block']: # Block of statements
            [block] = s.children
            decls, stats = block.children
            scope_env = {}
            for d in decls.children:
                (name,type) = type_declaration(d,type_env)
                scope_env[name] = type
            
            #print(f"scope_env: {scope_env}")
            for s in stats.children:
                if not type_statement(s,type_env + [scope_env]):
                    return False
            return True

        case ['lval', 'EQ', 'exp']: # Assignment
            lval, _, exp = s.children
            #print(f"{rule}: {lval} = {exp}")
            t1, t2 = type_lval(lval, type_env), type_exp(exp,type_env)
            if t1 is None:
                raise NameError(f"Variable {lval} referenced before definition")

            tm = max_type(t1,t2)
            if t1 != tm:
                raise TypeError(f"Assignment to {lval_name(lval)} of type {t1} with expression of type {t2}")
            return True
        
        case ['IF', 'exp', 'statement', 'statement']:
            _, exp, s1, s2 = s.children
            t = type_exp(exp,type_env)
            if t != 'cbit' and t != 'int':
                raise TypeError(f"Condition {show_exp(exp)} of if statement must be of type cbit or int (got {t})")
            
            t1, t2 = type_statement(s1,type_env), type_statement(s2,type_env)
            return t1 and t2
        
        case ['WHILE', 'exp', 'statement']:
            _, exp, s1 = s.children
            t = type_exp(exp,type_env)
            if t != 'cbit' and t != 'int':
                raise TypeError(f"Condition of while statement must be of type cbit or int (got {t})")
            
            return type_statement(s1,type_env)
        
        case ['qupdate']:           # Quantum update
            [qupdate] = s.children
            return type_qupdate(qupdate,type_env)
        
        case ['qupdate','IF','lval']:# Conditional quantum update
            [qupdate,_,lval] = s.children
            t = type_lval(lval,type_env)
            if t != 'qbit':
                raise TypeError(f"Condition of quantum conditional statement {show_statement(s)} must be of type qbit (got {t})")
            return type_qupdate(qupdate,type_env)

        case ['MEASURE','lval','lval']: # qbit measurement
            [_,qbit,cbit] = s.children
            tq, tc = type_lval(type_env,qbit), type_lval(type_env,cbit)
            if tq != 'qbit':
                raise TypeError(f"First argument to measure must be a qbit (got {tq})")
            if tc != 'cbit':
                raise TypeError(f"Second argument to measure must be a cbit (got {tc})")
            return True
        
        case ['procedure_call']:
            [procedure_call] = s.children
            name, lvals = procedure_call.children
            params = lookup_lval(name, type_env)  # Procedure parameters: list of (name, type) pairs.
            args   = [type_lval(l,type_env) for l in lvals.children] # Call arguments: list of types.
            
            # Check procedure call: number of arguments, sizes, and types must match.
            if len(params) != len(args):
                raise ValueError(f"Procedure {name} expects {len(params)} arguments, got {len(args)} ({params} vs {args})")
            
            psizes = [array_size(t) for (n,t) in params]
            asizes = [array_size(t) for t in args]

            type_correct = True
            for i in range(len(params)):
                (pn,pt), psz = params[i], psizes[i]
                at, asz = args[i], asizes[i]

                tp = None if psz is None else 'int' if psz.isnumeric() else 'symbolic'
                ta = None if asz is None else 'int' if asz.isnumeric() else 'symbolic'                

                match([tp,ta]):
                    case ['int','int']: # Good if sizes match
                        type_correct &= (int(psz) == int(asz))
                    case ['symbolic','int'] | ['int','symbolic'] | ['symbolic','symbolic'] | [None,None]: 
                        # Always good
                        type_correct &= True
                    case [_,_]:                              
                        # All remaining cases are bad.
                        type_correct = False

                if not  type_correct:
                    raise TypeError(f"Procedure {name} expects argument {pn} of type {pt}, got {show_lval(lvals.children[i])}: {at}")
            return True

def type_binop(t1,op,t2):
    match(op):
        case '+' | '-' | '*'| '%'|'**': 
            return max_type(t1,t2)
        case '/':
            return 'float'
        case '==' | '!=' | '<' | '>' | '<=' | '>=':
            if max_type(t1,t2) is None:
                return None
            else:
                return 'cbit'
        case _:
            raise Exception(f"type_binop: Unrecognized operator {op}")
    


def type_exp(e,type_env):
    # Is this a terminal (a leaf node), or does e have children?
    match(node_name(e)):
        case 'INT':    return 'int'
        case 'FLOAT' | 'NAMED_CONSTANT':  return 'float'
        
    # e has children to process.
    rule = node_rule(e, "expression")
    #print(f"type_exp: {rule} for {show_exp(e)}")
    try:
        match(rule):
            case ['exp']:
                [e1] = e.children
                return type_exp(e1,type_env)            

            case ['lval']:
                [e1] = e.children
                return type_lval(e1,type_env)
            
            case ['UNOP', 'exp']:       # Unary operation
                unop, e1 = e.children
                return type_exp(e1,type_env)
        
            case ['exp','BINOP','exp']: 
                e1,binop,e2 = e.children
                t1,t2 = type_exp(e1,type_env), type_exp(e2,type_env)
                t = type_binop(t1,binop,t2)
                if(t is None): 
                    raise TypeError(f"Incompatible types {t1} and {t2} in {rule}")
                return t
            
            case  ['exp','CMP','exp']:
                e1,cmp,e2 = e.children
                t1,t2 = type_exp(e1,type_env), type_exp(e2,type_env)
                tm = max_type(t1,t2)
                if(tm is None): 
                    raise TypeError(f"Incompatible types {t1} and {t2} in {rule}")
                return 'cbit'

            case ['BUILTIN_FUN1', 'exp']:
                fun, e1 = e.children
                t1 = type_exp(e1,type_env)
                
                match(t1):
                    case 'int' | 'float' | 'cbit': 
                        return 'float'
                    case _:   
                        raise TypeError(f"Argument to builtin function {fun} is of type {t1}, must be convertible to float.")
            
            case ['BUILTIN_FUN2', 'exp', 'exp']:
                fun, e1, e2 = e.children
                t1, t2 = type_exp(e1,type_env), type_exp(e2,type_env)

                tm = max_type(t1,t2)
                if(tm is None): 
                    raise TypeError(f"Argument to builtin function {fun} is of type {t1} and {t2}, must be convertible to float.")                
                else: 
                    return 'float'
            
            case ['INT']:
                return 'int'
            case ['FLOAT'] | ['NAMED_CONSTANT']:
                return 'float'

                
    except:        
        raise Exception(f"Error evaluating rule {rule} for node {e}") 

    raise  Exception(f"type_exp: {rule} not implemented")

def type_declaration(d,type_env):

    rule = node_rule(d, "declaration")

    match(rule):
        case ['TYPE','lval']:     # Scalar or array-declaration without initialization (0-initialize)
            type, lval = d.children
            lval_rule = [node_name(c) for c in lval.children]
            match(lval_rule):
                case ['ID']: 
                    [name] = lval.children
                    return (f"{name}", f"{type}")
                case ['ID','INT']: 
                    [name,size] = lval.children
                    return (f"{name}", f"{type}[{size}]")
                case ['ID','exp']:
                    [name,size] = lval.children
                    t = type_exp(size,type_env)
                    if t != 'int':
                        raise TypeError(f"Array {name} declared with size {size} but initialized with expression of type {t}")
                    return (f"{name}", f"{type}[{size}]")
                case _: 
                    raise Exception(f"type_declaration: Unrecognized rule {lval_rule} in lval {lval}")
                
        case ['TYPE','ID','exp']: # Scalar declaration with initialization
            type, name, exp = d.children
            t = type_exp(exp,type_env)
            tm = max_type(type,t)
            if type != tm:
                raise TypeError(f"type_declaration: Declaration of {name} of type {type} initialized with expression of type {t}")
            return (f"{name}", f"{type}")

        case ['TYPE','ID','exp','exps'] | ['TYPE','ID','INT','exps']: # Array declaration with initialization 
            type, name, exp_size, values = d.children
            size     = literal_eval(exp_size)
            t_values = [type_exp(e,type_env) for e in values.children]

            if (len(values.children) != size):
                raise ValueError(f"Array {name} declared with size {size} but initialized with {len(values.children)} values")
            
            for t in t_values:
                tm = max_type(type,t)
                if type != tm:
                    raise TypeError(f"Array {name} declared with type {type} initialized with expression of type {t}")

            return (f"{name}", f"{type}[{size}]")


# Extract declaration type without type-checking (i.e. does not assert valid types in subex, and hence doesn't need type_env)
def typeof_declaration(d):
    rule = node_rule(d, "declaration")
    match(rule):
        case ['TYPE','lval']:     # Scalar or array-declaration without initialization (0-initialize)
            type, lval = d.children
            lval_rule = [node_name(c) for c in lval.children]
            match(lval_rule):
                case ['ID']: 
                    [name] = lval.children
                    return (f"{name}", f"{type}")
                case ['ID','INT']: 
                    [name,size] = lval.children
                    return (f"{name}", f"{type}[{size}]")
                
        case ['TYPE','ID',_]: # Scalar declaration with initialization
            type, name, exp = d.children
            return (f"{name}", f"{type}")

        case ['TYPE','ID',_,'exps'] | ['TYPE','ID','INT','exps']: # Array declaration with initialization 
            type, name, exp_size, values = d.children
            size     = literal_eval(exp_size)
            return (f"{name}", f"{type}[{size}]")
        

def type_gate(g,type_env):
    rule = node_rule(g, "gate")
    match(rule):
        case ['NOT'] | ["H"]: return True
        case ["rgate",_]:
            rgate, angle_exp = g.children
            t = type_exp(angle_exp,type_env)
            if max_type(t,"float") != "float":
                raise TypeError(f"Angle in rotation gate {show_gate(g)} must be a float, got {t}")
        case _:
            raise Exception(f"Unrecognized rule {rule} in gate {g}")    


def type_qupdate(q,type_env):
    rule = node_rule(q, "qupdate")
    match(rule):
        case ['gate', 'lval']:
            [gate,lval] = q.children
            t1 = type_gate(gate,type_env)
            t2 = type_lval(lval,type_env)
            #print(f"t1 = {t1}, t2 = {t2}")
            if t2 != 'qbit':
                raise TypeError(f"Target of quantum gate must be a qbit (got {t2})")
            return True
        case ['lval','swap','lval']:
            [lval1,_,lval2] = q.children
            t1 = type_lval(lval1,type_env)
            t2 = type_lval(lval2,type_env)
            if t1 != 'qbit' or t2 != 'qbit':    
                raise TypeError(f"Arguments to swap must be qbits (got {t1} and {t2})")
            return True



                
                
        



