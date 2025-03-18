from copy import deepcopy
from lark.tree import Tree
from lark.lexer import Token
import numpy as np

from helpers import *
from show import *
from type import *
from PE import evaluate_exp, PE_lval

# simulate_program takes a #CQ- program as input: A single procedure with a single flat block of declarations and qupdate statements
# This is the result of partially evaluating all the classical parts away from a CQ program and flattening using flatten.py.
# Currently measurement and cbits are not included. The result is a matrix that represents the unitary operator for the full program.

# qbits_env is maps variable names to their index in the d-qubit basis set, where d is the total number of qubits in the program (input + auxiliary in block scope)

def simulate_program(P):
    procedures = P.children
    assert(len(procedures) == 1) # Only one procedure should be left after partial evaluation
    
    main = procedures[0]
    main_name, main_params, main_stat = main.children
    main_block = main_stat.children[0]
    assert(main_block.data == 'block')
    
    qbits_env = procedure_qbits_env(main)

    d = len(qbits_env)
    M = np.eye((2**d), dtype=complex).reshape([2]*(2*d))
    
    decls, stats = main_block.children    
    for s in stats.children:
        M = simulate_statement(s, qbits_env, M)

    return M
    
# 1+2-qubit matrix helper functions
# Single-qubit gate semantics
def gate_matrix(gate):
    rule = node_rule(gate, "gate")
    match(rule):
        case ['X'] | ['NOT']: 
            return np.array([[0,1],[1,0]], dtype=complex)
        case ['SX']: 
            return np.array([[1+1j,1-1j],[1-1j,1+1j]], dtype=complex)/2
        case ['H']:   
            return np.array([[1,1],[1,-1]],dtype=complex)/np.sqrt(2)
        case ['rgate','exp']: 
            [rgate, angle_exp] = gate.children
            rtoken = rgate.children[0]

            try:
                angle = evaluate_exp(angle_exp, {})                
            except Exception as e:
                raise Exception(f"gate_matrix: Cannot evaluate angle {show_exp(angle_exp)} in {show_gate(gate)}")
            
            match(rtoken.value):
                case 'Rx':
                    return np.array([[np.cos(angle/2),-1j*np.sin(angle/2)],[-1j*np.sin(angle/2),np.cos(angle/2)]],dtype=complex)
                case 'Ry':
                    return np.array([[np.cos(angle/2),-np.sin(angle/2)],[np.sin(angle/2),np.cos(angle/2)]],dtype=complex)
                case 'Rz':
                    return np.array([[np.exp(-1j*angle/2),0],[0,np.exp(1j*angle/2)]],dtype=complex)
        case _:
            raise Exception(f"gate_matrix: Unrecognized rule {rule} in {show_gate(gate)}")

# Direct sum of two matrices 
def direct_sum(A,B):
    m,n = A.shape
    p,q = B.shape
    return np.block([[A,np.zeros((m,q))],[np.zeros((p,n)),B]])

# Controlled gate semantics is just direct sum 
def controlled_matrix(G):
    IG = direct_sum(np.eye(2),G)
    return IG.reshape((2,2,2,2))

# Produce map from variable names to qubit indices
def procedure_qbits_env(main):
    main_name, main_params, main_stat = main.children
    main_block = main_stat.children[0]
    assert(main_block.data == 'block')
    try:
        decls, stats = main_block.children
    except:
        print(main_block)
        assert(False)

    qbit_input     = params_of_type(main_params,'qbit')
    qbit_auxiliary = decls_of_type(decls,'qbit')

    qbits_env = {}
    ix = 0
    for (name,size) in list(qbit_input) + list(qbit_auxiliary):
        if size == 1:
            qbits_env[name] = ix
            ix += 1
        else:
            for i in range(size):
                qbits_env[f"{name}[{i}]"] = ix
                ix += 1
    return qbits_env

# Simulate a single qupdate statement as effect on d-qubit operator matrix M:
# - Single-qubit gate: Compute gate 2x2 matrix and compute effect on M using tensor contraction
# - SWAP: Swap qubits k and l by swapping axes in M (could also be done less efficiently using a 2x2x2x2 tensor and tensor contraction)
def simulate_qupdate(qup, qbits_env, M):
    rule = node_rule(qup, "qupdate")

    try:
        match(rule):
            case ['gate','lval']:  # Single-qubit gate
                [gate, lval] = qup.children
                G = gate_matrix(gate)
                qbit_full_name = show_lval(lval)
                qbit_k = qbits_env[qbit_full_name]
                return np.tensordot(G,M, axes=([0],[qbit_k]))
                
            case ['lval','SWAP','lval']: # Array variable
                [lval1,_,lval2] = qup.children
                s1, s2 = show_lval(lval1), show_lval(lval2)
                qbit_k, qbit_l = qbits_env[s1], qbits_env[s2]
                return M.swapaxes(qbit_k,qbit_l)
                
            case _:
                raise Exception(f"simulate_qupdate: Unrecognized rule {rule} in {show_qupdate(qup)}")
    except Exception as e:
        print(f"simulate_qupdate: {e} when evaluating {rule} in {qup.pretty()}")
        raise e

# Simulate a 2-qubit controlled qupdate statement as effect on d-qubit operator matrix M
def simulate_controlled_qupdate(qup, control_lval, qbits_env, M):
    rule = node_rule(qup, "qupdate")
    
    try:
        control_full_name = show_lval(control_lval)    
        control_k = qbits_env[control_full_name]

        match(rule):
            case ['gate','lval']:  # Single-qubit gate
                [gate, target_lval] = qup.children

                G  = gate_matrix(gate)
                IG = controlled_matrix(G)

                target_full_name  = show_lval(target_lval)

                target_k  = qbits_env[target_full_name]

                return np.tensordot(IG,M, axes=([0,1],[control_k,target_k]))
            
            case ['lval','SWAP','lval']: # Array variable
                [lval1,_,lval2] = qup.children
                s1, s2 = show_lval(lval1), show_lval(lval2)
                qbit_k, qbit_l = qbits_env[s1], qbits_env[s2]

                Gswap  = (np.eye(4).reshape((2,2,2,2)).swapaxes(1,2).swapaxes(2,3)).reshape((4,4))
                IGswap = direct_sum(np.eye(2),Gswap).reshape((2,2,2,2,2,2))

                return np.tensordot(IGswap,M, axes=([0,1,2],[control_k,qbit_k,qbit_l]))
            case _:
                raise Exception(f"simulate_controlled_qupdate: Unrecognized rule {rule} in {show_qupdate(qup)}")
    except Exception as e:
        print(f"simulate_controlled_qupdate: {e} when evaluating {rule} in {qup.pretty()}")
        raise e

def simulate_statement(s,qbits_env, M):
    rule = node_rule(s, "statement")
    
    try:
        match(rule):
            case ['lval', 'EQ', 'exp']: # Assignment
                [lval,EQ,exp]    = s.children
                raise Exception(f"simulate_statement: Assignment {show_lval(lval)} = {show_exp(exp)} not implemented")

            case ['IF', 'exp', 'statement', 'statement'] | ['WHILE', 'exp', 'statement'] | ['block'] | ['procedure_call']: 
                raise Exception(f"simulate_statement: Control flow {show_statement(s)} not implemented")                
                
            case ['qupdate']: # Single-qubit update
                [qupdate] = s.children
                return simulate_qupdate(qupdate, qbits_env, M)
                            
            case ['qupdate','IF','lval']:
                [qupdate,IF,control_lval] = s.children
                return simulate_controlled_qupdate(qupdate, control_lval, qbits_env, M)
                
            case ['MEASURE','lval','lval']:
                raise Exception(f"simulate_statement: MEASURE {show_statement(s)} not implemented")
            
            case _:
                raise Exception(f"simulate_statement: Unrecognized rule {rule} in {show_statement(s)}")
    except Exception as e:
        print(f"simulate_statement: {e} when evaluating {rule} in {s.pretty()}")
        raise e

