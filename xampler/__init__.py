"""
The xampler module is built from xorro and contains functions to solve logic programs with parity
constraints. This implementation is taylored for sampling and counting

Classes:
Application -- Main application class.

Functions:
main  -- Main function starting an extended clingo application.
"""

from . import util
from . import transformer as _tf
from .countp import CountCheckPropagator
from .watches_up import WatchesUnitPropagator
from random import sample
import sys as _sys
import os as _os
import clingo as _clingo
from textwrap import dedent as _dedent

def translate_binary_xor(backend, lhs, rhs):
    aux = backend.add_atom()
    backend.add_rule([aux], [ lhs, -rhs])
    backend.add_rule([aux], [-lhs,  rhs])
    return aux

def transform(prg, files):
    with prg.builder() as b:
        files = [open(f) for f in files]
        if len(files) == 0:
            files.append(_sys.stdin)
        _tf.transform((f.read() for f in files), b.add)
            

def translate(mode, prg):
    if mode == "count":
        prg.add("__count", [], _dedent("""\
            :- { __parity(ID,even,X) } = N, N\\2!=0, __parity(ID,even).
            :- { __parity(ID,odd ,X) } = N, N\\2!=1, __parity(ID,odd).
            """))
        prg.ground([("__count", [])])

    elif mode == "countp":
        prg.register_propagator(CountCheckPropagator())

    elif mode == "up":
        prg.register_propagator(WatchesUnitPropagator())

    else:
        raise RuntimeError("unknow transformation mode: {}".format(mode))

class Application:
    """
    Application object as accepted by clingo.clingo_main().

    Rewrites the parity constraints in logic programs into normal ASP programs
    and solves them.
    """
    def __init__(self, name):
        """
        Initializes the application setting the program name.

        See clingo.clingo_main().
        """
        self.program_name = name
        self.version = "1.0"
        self.__approach = "countp"
        self.__s = 0
        self.__q = 0.5
        self.__sampling = _clingo.Flag(False)
        self.__display  = _clingo.Flag(False)
        self.__tolerance  = 0.8
        self.__confidence = 0.2
        self.__approxmc = _clingo.Flag(False)

    def __parse_approach(self, value):
        """
        Parse approach argument.
        """
        self.__approach = str(value)
        return self.__approach in ["count", "countp", "up"]

    def __parse_s(self, value):
        """
        Parse s value as the number of xor constraints.
        """
        self.__s = int(value)
        return self.__s >=0

    def __parse_q(self, value):
        """
        Parse the q argument for random xor constraints.
        """
        self.__q = float(value)
        return self.__q >0.0 and self.__q <=1.0

    def __parse_tolerance(self, value):
        """
        Parse the tolerance value
        """
        self.__tolerance = float(value)
        return self.__tolerance >0 and self.__tolerance <=1.0

    def __parse_confidence(self, value):
        """
        Parse the confidence value
        """
        self.__confidence = float(value)
        return self.__confidence >0 and self.__confidence <=1.0
    
    def register_options(self, options):
        """
        Extension point to add options to xorro like choosing the
        transformation to apply.

        """
        group = "Xampler Options"
        options.add(group, "approach", _dedent("""\
        Sampling with XOR constraints [countp]
              <arg>: {count|countp|up}
                count      : Add count aggregates modulo 2
                countp     : Propagator simply counting assigned literals
                up         : Propagator implementing unit propagation"""), self.__parse_approach)
        
        options.add_flag(group, "sampling", _dedent("""\
        Enable sampling by generating random XOR constraints"""), self.__sampling)

        options.add(group, "s", _dedent("""\
        Number of XOR constraints to generate. Default=0, log(#atoms)"""), self.__parse_s)

        options.add(group, "q", _dedent("""\
        Density of each XOR constraint. Default=0.5"""), self.__parse_q)

        options.add_flag(group, "display", _dedent("""\
        Display the random XOR constraints used in sampling"""), self.__display)

        options.add_flag(group, "approxmc", _dedent("""\
        Enable approximate model counting in ASP"""), self.__approxmc)

        options.add(group, "tolerance", _dedent("""\
        Tolerance value. Default=0.8"""), self.__parse_tolerance)

        options.add(group, "confidence", _dedent("""\
        Confidence value. Default=0.2"""), self.__parse_confidence)

    def main(self, prg, files):
        """
        Implements the rewriting and solving loop.
        """
        models = []

        """
        Sampling features before grounding/solving
        Building random parity constraints and configure clingo control
        """
        add_theory = True
        
        if self.__sampling.value:
            smp = _clingo.Control()
            selected = []
            requested_models = int(str(prg.configuration.solve.models))
            prg.configuration.solve.models = 0

            s = self.__s
            q = self.__q
            xors = util.generate_random_xors(smp, files, s, q)
            add_theory = False
            if self.__display.value:
                print(xors)
            files.append("examples/__temp_xors.lp")
        
            """
            Standard xampler workflow
            """
            transform(prg,files)
            prg.ground([("base", [])])
            translate(self.__approach, prg)
            ret = prg.solve(None, lambda model: models.append(model.symbols(shown=True)))

            """
            Sample from all answer sets remaining in the cluster
            """
            if self.__sampling.value:            
                _os.remove("examples/__temp_xors.lp")
                if requested_models == -1:
                    requested_models = 1
                elif requested_models == 0:
                    requested_models = len(models)
                if str(ret) == "SAT":
                    if requested_models > len(models):
                        requested_models = len(models)
                    selected = sorted(sample(range(1, len(models)+1), requested_models))
                    print("")
                    print("Sampled Answer Set(s): %s"%str(selected)[1:-1])
                    for i in range(requested_models):
                        print("Answer: %s"%selected[i])
                        print(' '.join(map(str, sorted(models[selected[i]-1]))))

        elif self.__approxmc.value:
            """
            ApproxMC algorithm
            """

            models = []
            counter = 0
            C = []
            pivot = int(round(2 * util.compute_threshold(self.__tolerance)))
            print("pivot: %s"%pivot)
            """
            Standard xorro workflow asking for pivot + 1 answer sets
            """
            prg_ = _clingo.Control()
            prg_.configuration.solve.models = pivot + 1
            transform(prg_,files)
            prg_.ground([("base", [])])
            ## Get the number of variables
            variables = [atom.symbol for atom in prg_.symbolic_atoms if atom.is_fact is False and "__parity" not in str(atom.symbol)]
            print("Number of variables (symbols): %s"%len(variables))
            translate(self.__approach, prg_)
            ret = prg_.solve(None, lambda model: models.append(model.symbols(shown=True)))

            if len(models) <= pivot and ret.exhausted:
                print("Exact count: %s answer sets"%len(models))

            else:
                print("NOT Exact count... There are more than %s answer sets"%(len(models)))
                
                n = len(variables)
                t = int(util.compute_itercount(self.__confidence))                
                print("pivot: %s"%pivot)
                
                while True:
                    ## Solve with XORs
                    counter +=1
                    print("\nIter: %s"%counter)
                    l = util.get_l(pivot)## Consider to move this out. This is constant
                    i = round(l - 1) ## Consider to move this out. This is constant
                    xor = ""
                    while True:                        
                        i += 1
                        
                        models = []

                        ## Create new clingo control object
                        prg_ = _clingo.Control()
                        ## Ask for pivot + 1 answer sets
                        prg_.configuration.solve.models = pivot + 1

                        ## Build xor
                        xor += util.get_xor(variables, int(i-l)+1)
                        filename = "examples/approx_mc_xors.lp"
                        f = open(filename, "w") ## append?
                        f.write(xor)
                        f.close()

                        """
                        Standard xampler workflow
                        """
                        transform(prg_,files+[filename])
                        prg_.ground([("base", [])])
                        translate(self.__approach, prg_)
                        ret = prg_.solve(None, lambda model: models.append(model.symbols(shown=True)))

                        ## SAT, UNSAT or number of modesl greater than pivot
                        if len(models) == 0 or len(models) > pivot:
                            if str(ret) == "UNSAT":
                                print("  i: %s, l: %s, m: %s | Solving with %s xors, %s Discarding solution... "%(i,l, i-l,len(xor.splitlines()), ret))
                                break
                            elif str(ret) == "SAT":
                                print("  i: %s, l: %s, m: %s | Solving with %s xors, %s Discarding solution... there are more answer sets than pivot value (%s)"%(i,l, i-l,len(xor.splitlines()),ret,pivot))
                        
                        elif (len(models)>=1 and len(models) <= pivot) or (i == n):
                            print("  i: %s, l: %s, m: %s | Solving with %s xors, %s Storing solution... there are less answer sets (%s) than pivot value (%s)"%(i,l, i-l,len(xor.splitlines()),ret,len(models),pivot))
                            print("  Partial Count = |S| * 2^(i-l) : %s"%int(len(models) * 2**(i-l)))
                            C.append(int(len(models) * (2**(i-l))))
                            break
                    
                    if counter == t:
                        break

                print("")
                print("Number of calls: %s, SAT: %s, UNSAT: %s"%(counter,len(C), counter-len(C)))
                print("List of all partial counts: %s"%C)
                final_count = int(util.get_median(C))
                print("")
                print("Approximate answer sets count: %s"%final_count)

        else:
            """
            Standard xampler workflow
            """
            transform(prg,files)
            prg.ground([("base", [])])
            translate(self.__approach, prg)
            ret = prg.solve(None, lambda model: models.append(model.symbols(shown=True)))

def main():
    """
    Run the xampler application.
    """
    _sys.exit(int(_clingo.clingo_main(Application("xampler"), _sys.argv[1:])))
