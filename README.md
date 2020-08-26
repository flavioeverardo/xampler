# xampler
An Answer Set-based Counting system based on [xorro](https://github.com/potassco/xorro).


[![standard-readme compliant](https://img.shields.io/badge/readme%20style-standard-brightgreen.svg?style=flat-square)](https://github.com/flavioeverardo/xampler)
[![License](http://img.shields.io/:license-mit-blue.svg)](http://doge.mit-license.org)


> A tool for approximate answer set counting with parity (XOR) constraints.
> A light version of `xorro` is presented using `clingo` 5 infrastructure with Python support.

## Description
`xampler` is a tool that takes the advantage of the flexible ASP infrastructure
by using the Python integration of `clingo` to solve random parity (XOR) constraints from different approaches. </br>
These approaches are: </br>
- count      : Add count aggregates with a modulo 2 operation
- countp     : Propagator simply counting assigned literals (default)
- up         : Propagator implementing unit propagation

The main idea for approximate counting is to use random XOR constraints on top of an ASP program
to cut through the search space towards "equal size" clusters. <br/>
This consist of calculating a few answer sets representative for all the search space.
This is particularly useful if the computation of all answers is practically infeasible.<br/>

`xampler` is based on the work from [2013 by Chakraborty et al.](https://link.springer.com/chapter/10.1007/978-3-642-40627-0_18)<br/>
Supratik Chakraborty, Kuldeep S. Meel, and Moshe Y. Vardi. **A Scalable Approximate Model Counter**


## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Input](#input)
- [Usage](#usage)
- [Examples](#examples)
- [Contributors](#contributors)
- [License](#license)


## Requirements

`xampler` works with `clingo` version 5.4
and is tested under Unix systems using Travis for Linux and Mac with Python 2.7 and 3.6. </br>
The easiest way to obtain Python enabled clingo packages is using Anaconda.
Packages are available in the Potassco channel.
First install either Anaconda or Miniconda and then run: `conda install -c potassco clingo`.



## Installation

Either run `xampler` directly from source or install it by the usual means provided by Python. </br>
To install `xampler` run: `python setup.py install`.



## Input

To accommodate parity constraints in the input language, we use the Aggregates-like syntax,
using a semicolon to separate elements that are themselves terms conditioned by conjunctions of literals. </br>
For example, let us express the XOR constraints `p(1) ⊕ ⊥`, and `p(2) ⊕ p(3) ⊕ ⊤` from the domain of `p(1..3)` as:
```
 &odd{ 1:p(1) }.
&even{ X:p(X), X>1 }.
```
The first constraint aims at filtering stable models that do not contain `p(1)`,
while the second requires that either none or both atoms `p(2)` and `p(3)` are true. </br>
The program obtained after running the XOR constraints with the choice rule ‘{p(1..3)}.’,
results in two stable models, viz. `{p(1)}`, and `{p(1), p(2), p(3)}`. </br>

It is important to remark that the scope for the XOR constraints presented in this version of `xampler`
corresponds to directive statements,
meaning they can neither occur in the body nor in the head of a rule
and thus act as meta statements instructing the ASP system to eliminate stable models violating the parity.



## Usage

To use `xampler` directly from source run `python -m xampler` from the project's root directory and
follow the standard-like clingo call:
`usage: xampler [number] [options] [files]`

 
```
xampler --help
xampler examples/test.lp --approach=countp
```

To enable the approximate counting features of `xampler` with the unit propagation approach, run the full command:
```
xampler examples/test.lp --approach=up --approxmc --tolerance=<n> --confidence<n> --outf=3
```

The `xampler` options for approximate counting are shown next:

| command | description |
|---|---|
| `--approxmc` | Enable approximate counting in ASP |
| `--tolerance=<n>` | The tolerance value to calculate the pivot value (cluster size). Default=0.8. |
| `--confidence=<n>` | Confidence value to calculate the number of iterations needed to approximate the count. Default=0.2. |


## Examples

To solve parity constraints on top of an ASP program, lets consider an example program `examples/basic.lp`. 
```
$ cat examples/basic.lp 
{a;b;c;d;e;f}.

&odd{a:a;d:d;e:e}.
&odd{b:b;e:e;f:f}.
&odd{c:c;d:d;e:e;f:f}.
&even{a:a;b:b}.
```

We call `xampler` from the command line, asking for all the answer sets. By solving the unrestricted choice rule with four parity constraints, we end with only four solutions.
```
$ python -m xampler examples/basic.lp 0
xampler version 1.0
Reading from examples/basic.lp
Solving...
Answer: 1
e
Answer: 2
c d f
Answer: 3
a b d e f
Answer: 4
a b c
SATISFIABLE

Models       : 4
Calls        : 1
Time         : 0.005s (Solving: 0.00s 1st Model: 0.00s Unsat: 0.00s)
CPU Time     : 0.005s
```

The approximate counting features allows `xampler` follows the work from [2013 by Chakraborty et al.](https://link.springer.com/chapter/10.1007/978-3-642-40627-0_18).
An example is shown below:
From an unrestricted choice from p(1) to p(10), we call xampler using the command below.
We use the clingo flag `--outf=3` to supress the standard clingo output.
For this simple example, the approximate count results to be the exact count.
```
{ p(1..10) }.
```

```
Number of variables (symbols): 10
pivot: 52
Solving...
NOT Exact count... There are more than 53 answer sets

Number of calls: 137, SAT: 136, UNSAT: 1

Approximate answer sets count (median)  : 1024
Approximate answer sets count (average) : 1024
```

## Contributors

* Flavio Everardo, Markus Hecher, Ankit Shukla - Get help/report bugs via the [issue tracker] </br>

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details


[issue tracker]: https://github.com/flavioeverardo/xampler/issues
