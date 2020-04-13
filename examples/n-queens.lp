%% n-Queens encoding
#const n = 11.

%% Optimized encoding from Running Clingo web example
{ q(I,1..n) } == 1 :- I = 1..n.
{ q(1..n,J) } == 1 :- J = 1..n.
:- { q(D-J,J) } >= 2, D =   2..2*n.
:- { q(D+J,J) } >= 2, D = 1-n..n-1.

#show q/2.
