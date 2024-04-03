# 3/4/2024: Data lab

The task today will be to add an optimization stage to your CQ compiler based on ZX calculus.

You are encouraged to use the PyZX library, which you install using `pip install pyzx`, and can read how to use here:  https://pyzx.readthedocs.io/en/latest/

The strategy for designing the optimization stage is:

1) Take the qiskit circuit that you have generated through your previous compilation steps and extract a ZX network from it (let's call it `qc`):

zxc = pyzx.Circuit.from_qasm(qc.qasm())

You can visualize it using PyZX to have a inspect the structure before optimizing:
pyzx.draw(zxc)

2) Perform your optimizing transformations using ZX rewrite rules (refer to https://pyzx.readthedocs.io/ and the paper). This is the central task. I suggest to inspect the intermediate results along the way. (For learning, apply the rewrite rules directly. In practice when simply using the library, to just get everything fully optimized, you can use `pyzx.simplify.full_optimize()`)

3) Extract the quantum circuit back from the optimized ZX network. This can then be passed to the next compiler stage, for topology mapping, etc.

qc_opt = zx.extract_circuit(g.copy())

# 27/3/2024: Reading material for 3/4 and rescheduling of 20/3

Robin Kaarsgaard Sales from SDU will lecture Wednesday 3/4 on ZX Calculus and circuit optimization. I will be there for the lab session to help out with your code as usual.

Once you have generated your quantum circuits, one way to optimize its performance is to extract a ZX network from the circuit, transform this network using the rules of ZX calculus, and finally extracting a quantum circuit from the optimized ZX network. 

To read before Wednesday 3/4:

The first 5 sections of John van de Wetering's "ZX-calculus for the working quantum computer scientist", which is found here: https://arxiv.org/pdf/2012.13966.pdf

Rescheduling of 20/3 to 19/4:

As I was down sick the whole week before Easter, I was unable to lecture on topology mapping 20/3. We will hold a replacement session to teach you about topology mapping on April 19th, 13:00-17:00. The material will be posted the week before.


# 13/3/2024: Datalab 13/3 and link to code

Today we will implement the synthesis stage of the quantum compiler. Each quantum computer architecture will only implement a small subset of gates with physical operations, and generate the remaining gates from these. In the synthesis stage, we transform the "full" gateset into this limited generator set.

Your output after partial evaluation for the two sample programs should be a list of quantum gate statements, but with nested blocks. Use the provided helper function `flatten_program` from `flatten.py` to transform into a single-block flat list of quantum operations.

Your task today: Synthesize the CQ qupdate (unconditional and controlled) to generate code for a quantum architecture Q that implements only the operations {X,SX,CX,RZ,measure}, which we will call "elementary gates".

Write a function that translates each single-qubit gate to a sequence of elementary gates.
Do the same for the 2-qubit controlled gates ("qupdate if qbit")
Generate Qiskit quantum circuits code for initialize.cq and qft2.cq with the classical part PE'd away.
(If you manage to get this far): Implement the general decomposition of 2x2 unitaries into Rz Ry Rz rotations.

The various helper code is on the github repository here: http://github.com/jamesavery/QCC

# 9/3/2024: Readling list for 13/3

In the coming week, we are going to implement the synthesis stage: transforming from a general set of quantum gates down to a small machine-dependent subset of elementary gates. I.e., we need to synthesize complex gates in terms of a limited gate set. In the data lab, we're going to transform our PE-generated intermediate code consisting of "machine instruction" gates for two different quantum computers with different physically implemented gate sets.

To read before Wednesday:

    Shende, Bullock and Markov: Synthesis of Quantum Logic Circuits: https://web.eecs.umich.edu/~imarkov/pubs/jour/tcad06-qsd.pdf
    Mogensen Chapter 8: Register allocation. This classical method is used to minimize the number of qubits needed by a program.

# 6/3/2024: Datalab assignment for 6/3

This week we're implementing (most of) a partial evaluator for CQ, which we use to evaluate away the classical parts of the programs, so that what remains is a "flat" quantum program in a simpler subset of CQ, which we will call CQ- ("CQ minus") and use as intermediate code. 

The files you need this week are on http://github.com/jamesavery/QCC - start by `git clone`ing it.

In the new file `showcq.py`, there are functions to print out a CQ AST back into CQ syntax, very useful for debugging.

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

The jupyter file `datalab6.3.ipynb` has helpful examples to test with.

I will also add a file with helpful hints to the github repository, which will be called `HINTS.md`. 

Happy hacking!

# 1/3/2024: Reading for 6/3

This coming week, we're going to build a partial evaluator (see Neil Jones's paper from last week) for our hybrid classical-quantum language CQ.  The classical types `int` and `float`,  take the role of statically bound variables, while `cbit` and `qbit` are dynamically bound. Your partial evaluator will take a CQ program and all classical input, interpret away the classical part, and produce a (much simpler) quantum program in our intermediate code language, CQ-. We'll also learn to deal with procedure calls and recursion, which we ignored last week.
Reading list before 6/3:

Chapter 6, Intermediate code. 6-6.5 (pages 133-145), 6.9-6.10 (pages 158-161)

Make sure to have read and understood Sections 1+2 of Neil's PE-paper: https://dl.acm.org/doi/pdf/10.1145/243439.243447

See you on Wednesday!

# 1/3/2024: On the exam in May

Dear all,

Some of you have asked about the exam in May.

The exam is based on the learning objectives and therefore also the general course objectives and contents listed in the DTU course base, https://kurser.dtu.dk/course/02196 . The exam will have a proportional mix of questions covering the different learning objectives and the questions will be of essay form.

The exam is a four hour exam with written material allowed.

Please do not hesitate to reach out of you have any further questions.

 
# 28/2/2024: Slides and Data lab problems 

Here are the slides from the first part of today's lecture, which includes the data lab problem descriptions. Enjoy!

http://www.nbi.dk/~avery/QCC/qcc2.pdf


# 21/2/2024: Topic and reading for next Wednesday, 28/2

Great to meet you all today!

Next week, we're going to introduce a small classical+quantum programming language 'CQ', being made up especially for you as you read this, which we will work towards building a full compiler for.

In the coming data lab, we're going to expand the expression parser and interpreter you made today (or are still making) to the full CQ language, including statements, multiple function declarations, and function calls. This is a fair deal more complex than expressions, so I suggest that you make sure to complete this week's work in good time to be ready for the next level on Wednesday. 

We're also going to learn Partial Evaluation (PE), a classical program transformation technique that we will use to generate code for  the quantum control. Assignment 1.6 from this week is a simple example of this. We'll read the first part of the linked paper by Neil Jones, a pioneer of automatic program analysis and transformation. (The rest of the paper deals with the real magic of partial evaluation: automatic compiler generation from interpreters, but sadly that's out of scope for this course).
Read the following before 28/2:

Mogensen Chapter 3: Symbol tables (5 pages)
Mogensen Chapter 4: Interpretation (9 pages)
Mogensen Chapter 5: Type checking 5-5.6 (8 pages)
Neil D. Jones: An Introduction to Partial Evaluation Sections 1+2 (6 pages)

Download it here: https://dl.acm.org/doi/pdf/10.1145/243439.243447

Looking forward to seeing you all again next Wednesday!

# 21/2/2024: Lecture slides from 21/2

Hi all,

Here are the slides from today's lecture. 

https://learn.inside.dtu.dk/d2l/common/viewFile.d2lfile/Database/MTg4MzUyNA/qcc1.pdf?ou=187805

# 19/2/2024: Data lab assignments for 21/2 

