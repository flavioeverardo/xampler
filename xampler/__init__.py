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
import datetime
from dateutil import relativedelta

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
            ## Clingo = Gringo + Clasp
            ## Gringo is the grounder. Is the language specific parser. Substitutes all the variables to domain specific values. In other words converts you ASP encoding into a propositional formula
            ## Clasp is the solver. Like a SAT solver, takes the formula and get the models.
            # Start
            startExTime  = datetime.datetime.now()      

            start  = datetime.datetime.now()
            end  = datetime.datetime.now()
            total_solving_time = relativedelta.relativedelta(end, start)
            models = [] ## Write all the answer sets
            counter = 0
            C = [] ## Append the partial counts
            display = self.__display.value  ## Flag for displaying or printing
            pivot = int(round(2 * util.compute_threshold(self.__tolerance))) ## Pivot
            """
            Standard xorro workflow asking for pivot + 1 answer sets
            """
            clingo_args = ["--warn=none"]  ## Disable Warnings and other clingo options. We could add this flag from the command line. Dont worry
            prg_ = _clingo.Control(clingo_args) ## Create clingo object. We might need this or not. Depends on How it is implemented
            prg_.configuration.solve.models = pivot + 1 ## Ask for a pivot + 1 answer sets. Setting clasp parameters
            transform(prg_,files) ## Tranforms input parity constraints from the language to facts. We might not need this.
            ## &odd{a} -> __partiy(ID, odd, a). or __parity(ID,even,a)
            ## At this time there is no parity constraint involved.
            ## Here we also process any input ASP encoding. For grounding.
            
            prg_.ground([("base", [])]) ## Call gringo and ground
            ## ASP encodings have variables and gringo instantiate all variables to a propositional formula
            ## atom(X) -> instantiated with the domain for example atom(1) or atom("a").
            
            ## Get the number of variables or unnasigned atoms. An atom could be set to True, False, or Undefined.
            ## We build parity constraints from undefined atoms. Or atoms that clasp will allocate in its partial assignments
            variables = [atom.symbol for atom in prg_.symbolic_atoms if atom.is_fact is False and "__parity" not in str(atom.symbol)]
            
            print("Number of variables (symbols): %s"%len(variables))
            print("pivot: %s"%pivot)
            ## Select the approach to solve and parse the __parity atoms to the specific xampler/xorro approach.
            translate(self.__approach, prg_)
            
            print("Solving...")
            ## Solving call. We append all the pivot+1 models into models
            ## The ret object, tell us if it is SAT, UNSAT, UNKOWNW
            ## Plain clasp solving without parity constraints
            # Start
            start  = datetime.datetime.now()
            ret = prg_.solve(None, lambda model: models.append(model.symbols(shown=True)))
            # End
            end  = datetime.datetime.now()
            # Elapsed
            difference = relativedelta.relativedelta(end, start)
            total_solving_time += difference
            hours   = difference.hours
            minutes = difference.minutes
            seconds = difference.seconds
            milliseconds = difference.microseconds/1000000
            print("Elapsed time: %s hours, %s minutes %s seconds %s milliseconds " %(hours, minutes, seconds, milliseconds))
    
            ## We check if the search space is exhausted. It means clasp has ennumerated ALL the models from the encoding.
            ## It means that the encoding has less anweer sets than Pivot, it means that clasp knows all the models and we can count all
            if len(models) <= pivot and ret.exhausted:
                print("Exact count: %s answer sets"%len(models))
            else:
                print("NOT Exact count... There are more than %s answer sets"%(len(models)))

                ## variables from the algorithm 
                n = len(variables) ## The number of variables. Unassinged atoms. Related to line 230
                t = int(util.compute_itercount(self.__confidence)) ## Compute the itercount

                ## Main loop
                while True:
                    ## Solve with XORs
                    counter +=1
                    if display:
                        print("\nIter: %s/%s"%(counter,t))
                    #print("Iter: %s/%s"%(counter,t))
                    ## l and i are symbols from the ApproxMC algorithm
                    l = util.get_l(pivot)## Get l
                    i = l# -1 ## Consider to move this out. This is constant
                    xor = "" ## Here is where we append the xors as theory atoms. If we do only propagator-based solutions, we dont need this. 

                    ## Inner loop
                    while True:
                        # Start
                        start  = datetime.datetime.now()
                        
                        i += 1 ## Increase i
                        
                        models = [] ## We clear the models list
                        
                        ## Create new clingo control object with no previous knowledge. Clean slate
                        prg_ = _clingo.Control(clingo_args)
                        ## Ask for pivot + 1 answer sets. Pivot is the size of the cell. 
                        prg_.configuration.solve.models = pivot + 1

                        ## Build xor as theory atoms. &odd{..} or &even{..}.
                        ## We write all the xors in a temporal file.
                        ## These xors are clingo-specific language XORs. We parsed them below
                        ## We build random XORs from unassinged variables of size i-l. 
                        xor_ = util.get_xor(variables, int(i-l), display) 
                        xor = xor_ ## Appending new xor for each solving step
                        filename = "__approx_mc_xors.lp"
                        f = open(filename, "w") ## append?
                        f.write(xor)
                        f.close()

                        """
                        Standard xampler workflow
                        """
                        ## Transform again parity constraints that gringo understands and thus clasp understands
                        ## &odd{a} -> __partiy(ID, odd, a). or __parity(ID,even,a)
                        transform(prg_,files+[filename])
                        ## Grounding as usual. This is gringo
                        prg_.ground([("base", [])])
                        translate(self.__approach, prg_) ## Selecting the approach again from the ones from xorro
                        ## Another solving call with parity constraints
                        ## the XOR module depends on the partial assignment from clasp. We just check that this partial assignment satisfies the XORs
                        ## Appending the models to the models list

                        ## Remove the temporal xor file
                        _os.remove(filename)

                        #print("Solving...")
                        ret = prg_.solve(None, lambda model: models.append(model.symbols(shown=True)))
                        # End
                        end  = datetime.datetime.now()
                        # Elapsed
                        difference = relativedelta.relativedelta(end, start)
                        total_solving_time += difference
                        hours   = difference.hours
                        minutes = difference.minutes
                        seconds = difference.seconds
                        milliseconds = difference.microseconds/1000000
                        #print("Elapsed time: %s hours, %s minutes %s seconds %s milliseconds " %(hours, minutes, seconds, milliseconds))
                        #print("%s" %(milliseconds))

                        ## SAT, UNSAT or number of modesl greater than pivot
                        ## Discarded runs. 
                        if len(models) == 0 or len(models) > pivot: ## Line 8 from algorithm 2
                            if str(ret) == "UNSAT":
                                if display:
                                    print("  i: %s, l: %s, m: %s | Solving with %s xors, %s Discarding solution... "%(i,l, i-l,len(xor.splitlines()), ret))
                                break ## Break
                            elif str(ret) == "SAT":
                                if display:
                                    print("  i: %s, l: %s, m: %s | Solving with %s xors, %s Discarding solution... there are more answer sets than pivot value (%s)"%(i,l, i-l,len(xor.splitlines()),ret,pivot))

                        ## Here it is SAT
                        ## If we are in the small cluster
                        elif (len(models)>=1 and len(models) <= pivot) or (i == n):
                            if display:
                                print("  i: %s, l: %s, m: %s | Solving with %s xors, %s Storing solution... there are less answer sets (%s) than pivot value (%s)"%(i,l, i-l,len(xor.splitlines()),ret,len(models),pivot))
                                print("  Partial Count = |S| * 2^(i-l) : %s"%int(len(models) * 2**(i-l)))
                                ## Do the partial count
                            C.append(int(len(models) * (2**(i-l))))
                            break

                    ## This is the outer break line condition.
                    if counter == t:
                        break

                ## We do the approximate count from the list C
                print("")
                print("Number of calls/iterations: %s, SAT: %s, UNSAT: %s"%(counter,len(C), counter-len(C)))
                if display:
                    print("")
                    print("List of all partial counts: %s"%C)
                    print("")
                    print("List of all sorted partial counts: %s"%sorted(C))
                median, average = util.get_median(C)
                print("")
                print("Approximate answer sets count (median)  : %s"%int(median))
                #print("Approximate answer sets count (average) : %s"%int(average))                
                # End
            endExTime  = datetime.datetime.now()
            # Elapsed
            differenceExTime = relativedelta.relativedelta(endExTime, startExTime)
            hours   = differenceExTime.hours
            minutes = differenceExTime.minutes
            seconds = differenceExTime.seconds
            milliseconds = differenceExTime.microseconds/1000000
            print("xampler Execution Time: %s hours, %s minutes %s seconds %s milliseconds " %(hours, minutes, seconds, milliseconds))
            # Elapsed            
            hours   = total_solving_time.hours
            minutes = total_solving_time.minutes
            seconds = total_solving_time.seconds
            milliseconds = total_solving_time.microseconds/1000000
            print("xampler Solving Time: %s hours, %s minutes %s seconds %s milliseconds " %(hours, minutes, seconds, milliseconds))

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
