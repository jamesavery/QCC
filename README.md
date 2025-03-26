# 26/3/2025: Advertisement!
If you enjoy the topic of quantum programming languages and quantum compilers, consider joining us this winter 
for Advanced Topics in Programming Languages: Hybrid Quantum-Classical Programming.
The course description is here: https://kurser.ku.dk/course/NDAK24007U (DIKU Block 2: November 17th to January 25th).

ATPL is an annual seminar course on up-to-date research topics in or directly related to
programming language theory and technology. Last year and next, the topic is hybrid quantum-classical programming models, HQC language-design, and HQC compiling techniques. However, you will individually get to choose a particular topic to delve into - either picked from a selection suggested by us, or chosen freely by yourself. The exam form is a written mini-project (and code where appropriate) with an oral defense. Especially if you want to do an MSc thesis on a related topic, this can be excellent preliminary work.


# 26/3/2025: Week 8 [Updated lab exercise info 25/3]
## Topic: Optimization techniques and the ZX Calculus

Robin Kaarsgaard Sales from SDU will lecture Wednesday 3/4 on ZX Calculus and circuit optimization. I will be there for the lab session to help out with your code as usual.

## Reading instructions:

The first 5 sections + the "ZX Cheat Sheet" in Appendix A from John van de Wetering's "ZX-calculus for the working quantum computer scientist", which is found here: https://arxiv.org/pdf/2012.13966.pdf

## Data lab
# 3/4/2024: Data lab

The task this week will be to add a small optimization stage to your CQ compiler based on ZX calculus.

Use the PyZX library, which you install using `pip install pyzx`, and can read how to use here:  https://pyzx.readthedocs.io/en/latest/

In the new file zx_semantics.py, you will find a small program for translating a flat CQ- AST into a PyZX circuit:
```
	zxc, qbit_env = zx_semantics(flattened_program)
```
which you can visualize using
```
   pyzx.draw(zxc)
```
and transform back into a CQ- program by using
```
   new_statements        = list(statements_from_zxc(zxc2,qbits_env))
   transformed_prog_tree = rewrite_Qprogram_statements(original_prog_tree,new_statements)
```
You will need to do a `git pull` to make sure you have the newest files.

### Exercises
1. Go through the steps in the notebook `datalab26.3.ipynb`: 
 - Parse and partially evaluate initialize.cq to the coefficients that yield `||a||^2 = 1/2 + 1/4 + 1/6 + 1/12 = 1`.
 - Build the PyZX circuit using zx_semantics and convert into a ZX diagram graph
 - Apply the ZX rewrite rules one by one until the ZX diagram is fully reduced
   (should remove all CNOT gates in this instance). In each step, refer to 
   Appendix A in https://arxiv.org/pdf/2012.13966.pdf and check the step by hand,
   in order to understand the tranformation. This is the main task.
 - Reconstruct the CQ- program and check that both the original program and the transform compute the correct amplitudes (using `simulate.py` as shown).
All this is contained in the notebook.
2. Add a ZX optimization stage in your CQ compiler before the routing stage, using the components from the notebook. 
3. Run for a variety of inputs and check that you get semantically equivalent transformed programs.


## Advertisement for Advanced Topics in Programming Languages: Hybrid Quantum-Classical Programming

If you found quantum compilers interesting, consider following our ATPL course on Hybrid Quantum-Classical programming in the fall:
https://kurser.ku.dk/course/ndak24007u/2024-2025

This is a course with a high degree of self-determination, as you will be able to choose a topic yourself to delve into and present in a mini-project. It is particularly useful in preparation for writing a master's thesis. 


# 19/3/2025: Week 7 [slides and data lab assignments updated @ 15:10]
## Reading instructions:

This week's lecture will be on Topology Mapping and the Routing problem for running quantum programs on existing hardware with limited
entanglement-connectivity. Almost all quantum device architectures allow entanglement only between "neighbour" qubits in some topology.
Thus, to perform a CNOT, we need to first move the control and target qubits through a series of SWAP (=3xCNOT) to become neighbours. Doing this optimally is an NP hard problem, and is one of the current roadblocks standing in the way of quantum advantage.

The lecture from today is here: http://www.nbi.dk/~avery/QCC/qcc6.pdf

Reading material:

Peham, Burgholzer, and Wille: "Optimal subarchitectures for Quantum
Circuit Mapping". https://arxiv.org/pdf/2210.09321

Zulehner, Paler, and Wille: "An Efficient Methodology for Mapping
Quantum Circuits to the IBM QX Architectures".
https://arxiv.org/pdf/1712.04722

## Data lab:

We will work on completing the gate synthesis code you started on last week, and extend it with CNOT routing for a simple topological qbit architecture. 

1. Implement the swap-rewrite transformation using 3xCNOT+4H.
2. Compile the qft2.cq program to the following architectures:
   2.1 a linear sub-architecture 0->1->2->...->d.
   2.2 a circular sub-architecture 0->1->2->...->d->0.
   
At each step, check that the matrix semantics are preserved using simulate_program from simulate.py (remember to apply it to the flattened program using flatten.py).

Please pull from git, as show.py has been updated, and simulate.py has been added.

Since many are still catching up on prior weeks, the main focus will be on getting up to speed (hence the simple assignment). Please don't hesitate to ask me for help also for work from prior weeks, or use the issues at https://github.com/jamesavery/QCC/issues as a forum for questions where you can help each other as well.

I have updated simulate.py, which allows you to compute the unitary matrix semantics of a pure quantum CQ- program without measurements. This allows you to test that any transformation you make is semantics-preserving: this is the case if and only if `simulate_program(P)` and `simulate_program(transform(P))` yields the same matrix. You can use this to test correctness both for your gate synthesis from last week, and the routed synthesis for this week.

# 18/3/2025: Fix for decomposition formula.

There was a mistake on the blackboard during the lecture when calculating the ZYZ-decomposition: numpy's atan2 is called as atan2(y,x), not atan2(x,y), so atan2(ra,rb) should be replaced by atan2(rb,ra) in the calculation of beta. See git issue https://github.com/jamesavery/QCC/issues/4.

# 17/3/2025: Elaboration on synthesis assignment

I have received some questions about the gate synthesis assignment, in particular what representation to use for the synthesized gates. 

The thought is to introduce new AST nodes for the instruction set (by defining a helper function similar to the other make_xxx in helpers.py), and rewrite the PE'd AST to replace the CQ gates with elementary "instruction set" gates. However, those of you who just generated a list of strings did fine as well - the goal is to learn how to do the synthesis (and it is very easy to adapt your code to generate nodes). Apologies for not making this clearer.

There is no need to modify the CQ.lark grammar file.

# 12/3/2025: Week 6

## Lecture: 

The PDF of the lecture is here:
http://www.nbi.dk/~avery/QCC/qcc4.pdf

Bjarnes pictures of the blackboard part of the lecture are here:
http://www.nbi.dk/~avery/QCC/blackboards/2025/w6.zip

## Reading:

This week, we are going to implement the synthesis stage: transforming from a general set of quantum gates down to a small machine-dependent subset of elementary gates. I.e., we need to synthesize complex gates in terms of a limited gate set. In the data lab, we're going to transform our PE-generated intermediate code consisting of "machine instruction" gates for two different quantum computers with different physically implemented gate sets.

To read before Wednesday:

     Shende, Bullock and Markov: Synthesis of Quantum Logic Circuits: 
     https://web.eecs.umich.edu/~imarkov/pubs/jour/tcad06-qsd.pdf
 
## Lab instrutions:

This week will implement the synthesis stage of the quantum compiler. Each quantum computer architecture will only implement a small subset of gates with physical operations, and generate the remaining gates from these. In the synthesis stage, we transform the "full" gateset into this limited generator set.

Your output after partial evaluation for the two sample programs should be a list of quantum gate statements, but with nested blocks. Use the provided helper function `flatten_program` from `flatten.py` to transform into a single-block flat list of quantum operations.

Your task: Synthesize the CQ qupdate (unconditional and controlled) to generate code for a quantum architecture Q that implements only the operations {X,SX,CX,RZ,measure}, which we will call "elementary gates".

     1. Write a function that translates each single-qubit gate to a sequence of elementary gates.
     2. Do the same for the 2-qubit controlled gates ("qupdate if qbit")[
     3. Generate quantum circuits code for initialize.cq and qft2.cq with the classical part PE'd away. Use the simulator from simulators.py to check the synthesized code.
     4. Implement the general decomposition of 2x2 unitaries into Rz Ry Rz rotations.
     
The various helper code is on the github repository here: http://github.com/jamesavery/QCC

There is a reference implementation of the CQ partial evaluator provided as `PEjames.py`, in case you didn't get your own to work.

# 5/3/2025: Week 5

## Lecture
Bjarnes pictures of the blackboard part of the lecture are here:
http://www.nbi.dk/~avery/QCC/blackboards/2025/w5.zip

## Topic overview:

Programs as data: Semantics-preserving program transformations.
CQ-: a small intermediate quantum sub-language.
Partial evaluation for quantum-program generation.

This coming week, we're going to build a partial evaluator that transforms a mixed classical-quantum CQ program to a pure quantum program in the CQ- sub-language. Partial evaluation is a semantics preserving program transformation, which we will learn about in today's lecture.

## Reading instructions:

1. Neil Jones: "An Introduction to Partial Evaluation" (First 8 pages)
https://dl.acm.org/doi/pdf/10.1145/243439.243447

2. Uwe Meyer: "Techniques for Partial Evaluation of Imperative
Languages" (Full paper, this is the technique you will use)
http://www.nbi.dk/~avery/QCC/PE-imperative.pdf

## Lab instructions:

This week we're implementing (most of) a partial evaluator for CQ, which we use to evaluate away the classical parts of the programs, so that what remains is a "flat" quantum program in a simpler subset of CQ, which we will call CQ- ("CQ minus") and use as intermediate code. 

The files you need this week are on http://github.com/jamesavery/QCC - start by `git clone`ing it.

In the new file `show.py`, there are functions to print out a CQ AST back into CQ syntax, very useful for debugging.

This week's task:

In PE-skeleton.py, I've provided both the easiest and most difficult parts - what's left for you to implement are declarations and expressions. 

1. Implement partial evaluation of declarations (PE_declaration(d,value_env)), and test on declaration examples.
2. Start on PE_statement(d,value_env) and implement assignments and quantum operations.
   Test on examples.
3. Implement blocks, test on examples.
4. Implement if-conditionals, and while-loops.
   What are considerations for how to partially evaluate conditionals and while-loops?
   Test on examples.

For full-program specialization, you can either use my implementation for program and procedures,
or implement your own (a bit tricky).

5. Once you have debugged the components, you should be able to to partially evaluate
   any CQ-program without function calls; in particular initialize.cq and qft2.cq

Notice that you get some unnecessary blocks, etc., that doesn't to anything in the residual code.
You can get rid of unnecessary nested blocks in the following way:
1. If the block contains no declarations, its statements can be merged directly back
   into the parent block.
2. If the block contains declarations with no name clashes in the parent block,
   i)  the declarations can be appended to the parent block's declarations, and
   ii) the statements can be merged in-place with the parent block's statements.
3. If the block contains declarations that clash with variables in the parent block's scope,
   append a unique suffix to the names and proceed like case 2.
In this way, you obtain a flat program consisting only of a single flat scope,
with variables declared at the top. Only loops that depend on quantum operations remain.

The jupyter file `datalab5.3.ipynb` has helpful examples to test with.


# 26/2/2025: Week 4

## Lecture
Here are the slides from today's lecture, which includes the data lab problem descriptions. Enjoy!

http://www.nbi.dk/~avery/QCC/qcc2.pdf


# 19/2/2025: Week 3
Here are the slides from today's lecture:

http://www.nbi.dk/~avery/QCC/qcc1.pdf
