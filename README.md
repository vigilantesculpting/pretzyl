# pretzyl
A simple Forth-like stack based interpreter

Pretzyl implements a simple Forth-like interpreter.
The interpreter accepts an dict-like Environment and a set of Operators.

Input is broken into words, separated by whitespace and/or string deliminators and brackets.
Special tokens that denote these are quotes [", '] and brackets [(, )]

Input starts with a fresh heap of stacks, containing a single stack.
Each input word is evaluated in turn:
- If it is an opening bracket, a new stack is pushed onto the heap of stacks.
- If it is a closing bracket, the top stack is removed, and its contents placed on the new top stack.
- If a word evaluates to an operator, the operator is applied to the stack.
- Otherwise, the word is simply placed on top of the current top stack.

Each stack forms its own scope. All values from lower scopes are available to upper scopes,
but a scope can only write variables and modify its own scope.

Once all words in a scope have been evaluated, the scopes's contents is returned to the caller.

Operators operate on the words on the stack. Typically, operators are binary or unary.
This means they operate on the top two (binary) words or the top (unary) word.
They place their results on top of the stack.

Words come in two types: references and literals.
Literals are numbers and strings.
References are names, that are looked up in the provided Environment, typically before
the operator works on them.

In general operators are applied once. Some operators are called Modifiers, they operate
on the last run operator, typically to repeat it.

Typically, operators are stored using bare names in the same environment as other variables.
Pretzyl can use a macro dictionary to optionally replace shortcut symbols with expanded
bare names. For example, by default 'sum' will expand to 'add squash', which will repeat
(squash) the preceding operator (add) until there are no more arguments in the scope.

## Examples

In the following examples, '>' shows the pretzyl program code.
The examples use the default operator set.
'=>' shows the program execution
'env <=' shows what the environment is set up as.

Example 1: Simple algebra:
```
	> 2 2 2 prod 4 sum
	=> 8 4 sum
	=> 12
```

Example 2: Nested algebra:
```
	> 2 (2 2 prod) 4 sum
	=> 2 4 4 sum
	=> 10
```

Example 3: With lookup:
```
	env <= {'name': 'Jack'}
	> 'hello ' name '!' sum
	=> 'hello Jack!'
```

Example 4: Filepath construction:
```
	env <= {'key': 'a7c34bd'}
	> 'static' 'css' ('site-' key '.html' sum) //+
	=> 'static' 'css' 'site-a7c34bd.html' //+
	=> 'static/css/site-a7c34bd.html'
```

## Usage:

The following code show how to use pretzyl from a python shell:

```python
	>>> from pretzyl import Pretzyl
	>>> env = {'key': 'a7c34bd'}
	>>> p = Pretzyl(env)
	>>> print p.eval("'static' 'css' ('site-' key '.html' sum) //+")
	static/css/site-a7c34bd.html
```
