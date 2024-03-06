from lark import *
from lark.tree import Tree
from lark.lexer import Token
from ast import literal_eval
import numpy as np
import sys

# Lark nodes can be Token (corresponding to TERMINALS) or Tree (corresponding to nonterminals).
# This helper function unifies the slightly different things you need to do to get their types: 
def node_name(t):
    if(is_numeric(t)):  return 'NUMERICAL_VALUE'
    if(type(t)==Token): return t.value if t.type == 'RULE' else t.type 
    if(type(t)==Tree):  return t.data if type(t.data)==str else t.data.value
    raise Exception(f"Unrecognized parse tree node: {t} with type {type(t)} ({type(t)==float}).")

# Helper function to get CQ-type from a python value
def numerical_type(v):
    if type(v) == bool:                      return "cbit"
    if type(v) == int or type(v) == np.int64: return "int"
    if type(v) == float or type(v) == np.float64: return "float"
    raise Exception(f"Unrecognized numerical type {type(v)} for {v}")


# Helper function for pattern matching on Lark parse trees
def node_rule(v, node_type=""):
    try:
        rule = [node_name(c) for c in v.children]
    except:
        raise Exception(f"Data error in {node_type} {v}")
    
    return rule

def is_numeric(x): 
    return (type(x) == bool or 
            type(x) == int or type(x) == float or 
            type(x) == np.float64 or type(x) == np.int64)

# Helper functions for interpretation
named_constants = {'pi': np.pi}

evaluate_binop = {
    '+': lambda x,y: x+y,
    '-': lambda x,y: x-y,
    '*': lambda x,y: x*y,
    '/': lambda x,y: x//y if type(x) == int and type(y) == int else x/y,    
    '%': lambda x,y: x%y,
    '&': lambda x,y: x&y,
    '|': lambda x,y: x|y,
    '^': lambda x,y: x^y,
    '<': lambda x,y: x<y,
    '==': lambda x,y: x==y,
    'xor': lambda x,y: x^y,
    '**': lambda x,y: x**y
}

evaluate_unop = {
'-':   lambda x: -x,
'~':   lambda x: ~x,
'not': lambda x: (not x)
}

evaluate_fun = {
'sin': np.sin, 
'cos': np.cos,
'tan': np.tan,
'arccos': np.arccos,
'arcsin': np.arcsin,
'arctan2': np.arctan2,
'exp': np.exp,
'sqrt': np.sqrt,
'random': np.random.random
}

# Auxiliary function to read in a text file and return content as a string:
def read_file(path):
    with open(path,'r') as f: return f.read()

# Helper functions for dealing with types and variables
def array_base(t):
    i = t.find('[')
    return t if i==-1 else t[:i]

def array_size(t):
    i = t.find('[')
    return None if i==-1 else t[i+1:-1]

def lval_name(l):
    if hasattr(l,'children'):
        if len(l.children) == 1: return f"{l.children[0]}"
        else: return f"{l.children[0]}[{l.children[1]}]"
    else:
        return f"{l}"
    
def lookup_lval(l, env):
    name = lval_name(l)
    #print(f"Looking up {name} in {env[1:]} (lval = {l})")
    for V in env[::-1]: # Look through variable scopes in reverse order
        if name in V: return V[l]
    return None

def lookup_scope(l, env):
    name = lval_name(l)
    #print(f"Looking up scope for {name} in {env} (lval = {l})")
    for i,V in enumerate(env[::-1]): # Look through variable scopes in reverse order
        if name in V: return len(env)-i-1
    return -1


def max_type(t1,t2):
    try:
        scalar_types = ['cbit','int','float']
        i1, i2 = [scalar_types.index(t) for t in [t1,t2]]
        return scalar_types[max(i1,i2)]
    except:
        return None

########### HELPER FUNCTION FOR BUILDING LARK AST NODES. ADD MORE AS NEEDED ############
# To make a new AST node, use 
#  - Token('<TOKEN-NAME>', value)                 for terminals, and 
#  - Tree(Token('RULE', '<rule-name>'), children) for nonterminals.
########################################################################################
from lark.tree import Tree
from lark.lexer import Token

def make_program(procedures):
    return Tree(Token('RULE', 'program'), procedures)

def make_procedure(name, parameters, statement):
    return Tree(Token('RULE', 'procedure'),  
                [name, Tree(Token('RULE','parameter_declarations'),parameters), statement])   

def make_skip_statement():
    return make_block([],[],False)
    #return Tree(Token('RULE','statements'), [Token('SKIP','skip')])

def make_block(declarations, statements, condense):
    #print(f"Making block with {len(declarations)} declarations and {len(statements)} statements (condense = {condense})")
#    if(condense):
#        match(len(statements)):
 #           case 0: 
 #               return make_skip_statement()
 #           case 1: 
 #               return statements[0]
        
    return Tree(Token('RULE','statement'),[Tree(Token('RULE', 'block'), 
                [Tree(Token('RULE', 'declarations'), [d for d in declarations if d != True]), 
                 Tree(Token('RULE', 'statements'),   [s for s in statements   if s != True])])])

