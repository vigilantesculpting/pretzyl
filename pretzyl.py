#!/usr/bin/env python

"""A simple Forth-like stack based interpreter

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
Once all words have been evaluated, the stack's contents is returned to the caller.

Operators operate on the words on the stack. Typically, operators are binary or unary.
This means they operate on the top two (binary) words or the top (unary) word.
They place their results on top of the stack.

Words come in two types: references and literals.
Literals are numbers and strings.
References are names, that are looked up in the provided Environment, typically before
the operator works on them.

Operators are non-greedy, and only run once.
Operators can be modified to run a specified number of times, or be greedy, in which
case they will operate until they fail (typically stack underflow or stack overflow)

Example 1: Simple algebra:
	2 2 2 ** 4 +*
	=> 8 4 +*
	=> 12

Example 2: Nested algebra:
	2 (2 2 **) 4 +*
	=> 2 4 4 +*
	=> 10

Example 3: With lookup:
	env = {'name': 'Jack'}
	'hello ' name '!' +*
	=> 'hello Jack!'

Example 4: Filepath construction:
	env = {'key': 'a7c34bd'}
	'static' 'css' ('site-' key '.html' +*) pathjoin*
	=> 'static' 'css' 'site-a7c34bd.html' pathjoin*
	=> 'static/css/site-a7c34bd.html'

Usage:
	>>> from pretzyl import Pretzyl
	>>> env = {'key': 'a7c34bd'}
	>>> p = Pretzyl(env)
	>>> print p.eval("'static' 'css' ('site-' key '.html' +*) pathjoin*")
	static/css/site-a7c34bd.html

"""

import shlex
import sys
import re

#import pdb

#For internal debug use
LOG = False

def log(*args, **kwargs):
	"""For internal debug use
	"""
	if LOG:
		for arg in args:
			sys.stderr.write(str(arg))
		sys.stderr.write("\n")


#######################################################################
# Utilities


class Reference:
	"""Defines a Reference token

	Tokens can be Literals or References.
	References are names, that refer to values in an Environment.
	We encapsulate them in this class before pushing the raw names (strings) onto the stack, so that
	we can distinguish them from Literals later on.

	Literals are used as-is (ie. strings are strings, booleans are booleans, and numbers are numbers).
	"""

	def __init__(self, name):
		self.name = name

	def __repr__(self):
		return "Reference(%s)" % str(self.name)

class BaseException(Exception):
	"""Base exception class for this module
	"""
	pass

class RecursionOverflow(BaseException):
	"""Recursion overflow

	This exception is raised when the stack depth exceeds the STACKDEPTH limit, ie. there 
	are too may heirarchical open brackets in the program
	"""
	pass

class NestingException(BaseException):
	"""Nesting exception

	This is raised when there are mismatched brackets in the program. Either one too many
	closing brackets, or too few closing brackets.
	In either case, the number and nesting of brackets do not match.
	This is a syntax error in the program.
	"""
	pass

class StackUnderflow(BaseException):
	"""Stack underflow

	Raised by the interpreter when an operation attempts to pop more values
	off the stack than are currently available.
	"""
	pass

class StackOverflow(BaseException):
	"""Stack overflow

	Raised by the interpreter when an operation attempts to push more values
	onto the stack than are currently allowed.
	"""
	pass

class IterationOverflow(BaseException):
	"""Iteration overflow

	Raised by the interpreter when a modified inf repeat operation does not terminate
	before the expected number of iterations.
	"""
	pass

class InvalidReference(BaseException):
	"""Invalid reference token lookup
	"""
	pass


class MalformedOperator(BaseException):
	"""Operator syntax error

	This is an internal exception that is used during operator parsing, to indicate
	that the operator (specifically, its modifier) is malformed, and that the 
	operator should be treated as a regular reference instead.
	"""
	pass


#######################################################################
# Default operators


class _DefaultOperators:
	"""Default operator set

	This is a utility class that contains a bunch of useful default operators.
	"""

	# TODO: clean up the logging instructions to something more sane.

	def isset(self, P):
		"""Tests whether a token is a valid reference to an entry in the environment.
		[a is in env]
		unary(n -> n')
		"""
		a = P.pop(lookup = False)
		c = P.validref(a)
		P.push(c)
	
	def greaterthan(self, P):
		"""Tests whether two tokens follow the greater-than ordering
		[a >= b]
		binary(m,n -> n')
		"""
		a, b = P.pop(2)
		c = a > b
		P.push(c)
	
	def lessthan(self, P):
		"""Tests whether two tokens follow the less-than ordering
		[a < b]
		binary(m,n -> n')
		"""
		a, b = P.pop(2)
		c = a < b
		P.push(c)

	def contains(self, P):
		"""Tests whether a token is not None, in the succeeding (collection) token
		[a in b]
		binary(m,n -> n')
		"""
		a, b = P.pop(2)
		c = a is not None and b in a
		P.push(c)
	
	def equals(self, P):
		"""Tests whether two tokens evaluate to the same content
		[a == b]
		binary(m,n -> n')
		"""
		a, b = P.pop(2)
		c = a == b
		P.push(c)

	def greaterequal(self, P):
		"""Tests whether two tokens follow the greater-or-equal ordering
		[a >= b]
		binary(m,n -> n')
		"""
		a, b = P.pop(2)
		c = a >= b
		P.push(c)

	def invert(self, P):
		"""Inverts the logical value of a token
		[not a]
		unary(n -> n')
		"""
		a = P.pop()
		c = not a
		log(a, "not =>", c)
		P.push(c)
	
	def and_(self, P):
		"""Tests whether two tokens both evaluate to true
		This is a short-circuiting test, if the first token is false the second is not evaluated.
		[a and b]
		binary(m,n -> n')
		"""
		b, a = P.pop(2, lookup = False)
		c = P.lookup(b) if P.lookup(a) else False
		P.push(c)
	
	def or_(self, P):
		"""Tests whether one of two tokens evaluates to true
		This is a short-circuiting test, if the first token is true the second is not evaluated.
		[a or b]
		binary(m,n -> n')
		"""
		b, a = P.pop(2, lookup = False)
		c =  P.lookup(b) if not P.lookup(a) else True
		P.push(c)
	
	def strftime(self, P):
		"""Applies the strftime method in the first token to the second token.
		[a.strftime(b)]
		binary(m,n -> n')
		"""
		a, b = P.pop(2)
		c = a.strftime(b)
		P.push(c)
	
	def truncate(self, P):
		"""Converts a token into words, and selectes the first N of these
		[trancatewords(a)]
		unary(n -> n')
		"""
		words = 25
		a = P.pop()
		"""Remove tags and truncate text to the specified number of words."""
		c = ' '.join(re.sub('(?s)<.*?>', ' ', a).split()[:words])
		P.push(c)
	
	def pathjoin(self, P):
		"""Joins two words together using the '/' separator
		This functions like os.path.join:
		- if the first token is empty, the second token is returned unchanged.
		- if the second token is empty, the first is returned with a trailing separator
		[os.path.join(a, b)]
		binary(m,n -> n')
		"""
		a, b = P.pop(2)
		c = b if len(a) == 0 else a + "/" + b
		P.push(c)

	def toreference(self, P):
		"""Creates a reference with a name from a literal
		[Reference(a)]
		unary(n -> n')
		"""
		a = P.pop()
		c = Reference(a)
		P.push(c)

	def multiply(self, P):
		"""Multiplies two tokens
		[a * b]
		binary(m,n -> n')
		"""
		a, b = P.pop(2)
		c = a * b
		P.push(c)

	def add(self, P):
		"""Adds two tokens
		[a + b]
		binary(m,n -> n')
		"""
		a, b = P.pop(2)
		c = a + b
		P.push(c)

	def subtract(self, P):
		"""Adds two tokens
		[a - b]
		binary(m,n -> n')
		"""
		a, b = P.pop(2)
		c = a - b
		P.push(c)

	def divide(self, P):
		"""Divides two tokens
		[a / b]
		binary(m,n -> n')
		"""
		a, b = P.pop(2)
		c = a / b
		P.push(c)


_DefaultOperatorSet = _DefaultOperators()

DefaultOperators = {
	'exists'		: _DefaultOperatorSet.isset,
	'>'				: _DefaultOperatorSet.greaterthan,
	'<'				: _DefaultOperatorSet.lessthan,
	'contains' 		: _DefaultOperatorSet.contains,
	'==' 			: _DefaultOperatorSet.equals,
	'>='			: _DefaultOperatorSet.greaterequal,
	'!' 			: _DefaultOperatorSet.invert,
	'and' 			: _DefaultOperatorSet.and_,
	'or' 			: _DefaultOperatorSet.or_,
	'strftime'  	: _DefaultOperatorSet.strftime,
	'truncate'		: _DefaultOperatorSet.truncate,
	'pathjoin' 		: _DefaultOperatorSet.pathjoin,
	'~' 			: _DefaultOperatorSet.toreference,
	'*' 			: _DefaultOperatorSet.multiply,
	'+' 			: _DefaultOperatorSet.add,
	'-' 			: _DefaultOperatorSet.subtract,
	'/' 			: _DefaultOperatorSet.divide,
}


###############################################################################
# The Pretzyl class


class Pretzyl:
	"""This is the core interpreter of Pretzyl

	It defines both the external API for a user to process a program with,a
	as well as the operator API with which operators (both default and custom)
	can interact with the stack.

	It processes a text program into tokens, evaluates each token in turn,
	and arranges the output on a heap of stacks. It also holds the environment,
	with which operators can interact using the stack.
	"""

	QUOTES = "'", '"'
	BOOLEANS = "True", "False"
	PUSHTOKEN = "("
	POPTOKEN = ")"

	STACKLIMIT = 256
	STACKDEPTH = 10
	INFLIMIT = 256 # set to float('Inf') for no limit

	def __init__(self, environment, operators = DefaultOperators):
		self.env = environment
		self.ops = operators
		self.modifiers = {
			"*": self.modifier_repeat,
		}

	def validref(self, token):
		"""Checks whether a token is a valid reference in the environment
		"""
		return isinstance(token, Reference) and token.name in self.env

	def lookup(self, token):
		"""Returns the value of a token in the environment
		If the token is a literal, its value is returned
		"""
		if isinstance(token, Reference):
			try:
				return self.env[token.name]
			except KeyError as e:
				raise InvalidReference
		return token

	def checkstack(self, minsize):
		"""Checks whether the stack as at least the required minsize length
		"""
		if len(self.stacks[-1]) < minsize:
			raise StackUnderflow

	def pop(self, count = 1, lookup = True):
		"""Returns the top count tokens in the stack
		The tokens are removed from the stack.
		They are returned in FIFO order, and if lookup is True,
		their values in the environment are looked up. 
		"""
		self.checkstack(count)
		if count > 0:
			# chop the last count items off the stack
			self.stacks[-1], items = self.stacks[-1][:-count], self.stacks[-1][-count:]
			assert(len(items) == count)
		else:
			# remove all items from the stack
			self.stacks[-1], items = [], self.stacks[-1]
		# do lookup, if required
		if lookup:
			items = [self.lookup(item) for item in items]
		# return 1, all or none
		return items[0] if len(items) == 1 else items if len(items) > 1 else None

	def push(self, value):
		"""Pushes a token onto the topmost stack
		"""
		if len(self.stacks[-1]) + 1 > self.STACKLIMIT:
			raise StackOverflow
		self.stacks[-1].append(value)

	def pushstack(self):
		"""Adds a stack to the heap of stacks
		The stack becomes the new active top stack.
		This is done when an opening bracket token is found.
		"""
		if len(self.stacks) + 1 > self.STACKDEPTH:
			raise RecursionOverflow
		self.stacks.append([])

	def popstack(self):
		"""Pops the top stack from the heap of stacks
		The contents of the stack is added to the new top stack.
		This is done when an closing bracket token is found.
		"""
		if len(self.stacks) == 1:
			raise NestingException
		laststack = self.stacks.pop()
		if len(laststack) == 1:
			self.push(laststack[0])
		elif len(laststack) > 1:
			self.push(laststack)
		else:
			pass

	def modifier_repeat(self, operator, arg):
		"""This modifier will repeat the given operator a number of times.
		If arg is a number, the operator is repeated that many times.
		If arg is empty, the operator is repeated until 
		- the stack is empty,
		- the stack overflows, or 
		- the iteration limit is reached.
		The first is a successful (and expected) outcome.
		The last two are failures in the program code.
		"""
		if len(arg) == 0:
			log("modifier_repeat: inf")
			stacksize = len(self.stacks[-1])
			log("stacksize: ", stacksize)
			i = 0
			while True:
				if i > self.INFLIMIT:
					# To prevent possibly infinite repetition of the
					# inf modifier, we limit it to INFLIMIT iterations.
					# If we hit this iteration limit without collapsing
					# the stack, this is an error.
					raise IterationOverflow
				i += 1
				try:
					operator(self)
				except StackUnderflow as e:
					# In this case (inf repeat modifier) we expect the 
					# operator to eventually starve the stack, so this is 
					# treated as an expected situation.
					break
				assert(len(self.stacks[-1]) < stacksize)
				stacksize = len(self.stacks[-1])
				log("new stacksize: ", stacksize)
		else:
			try:
				times = int(arg)
			except ValueError:
				raise MalformedOperator
			log("modifier_repeat: ", times)
			log("stack: ", len(self.stacks[-1]), self.stacks[-1])
			for i in range(times):
				log("modifier_repeat: iteration", i)
				log("stack: ", len(self.stacks[-1]), self.stacks[-1])
				operator(self)

	def makeoperator(self, token):
		"""This method attempts to make an operator (possibly with modifier) out of a token
		If succesful, the operator(+modifier) is executed, and the method returns True.
		Otherwise, the method returns False.
		"""
		if not isinstance(token, Reference):
			# simply return false, this is not a reference
			return False
		for name in self.ops.keys():
			if token.name.find(name) == 0:
				opname, modifier = token.name[:len(name)], token.name[len(name):]
				operator = self.ops[opname]
				break
		else:
			# no matching operator found, might be something else
			return False
		log("makeoperator: operator: ", operator, " modifier:", modifier)
		if len(modifier) == 0:
			operator(self)
			return True
		else:
			# might still be a valid reference (other than an operator!)
			modsym 	= modifier[0]
			arg 	= modifier[1:]
			if modsym in self.modifiers:
				mod = self.modifiers[modsym]
				try:
					mod(operator, arg)
					return True
				except MalformedOperator as e:
					pass
		return False

	def tokenize(self, line):
		"""This method attempts tokenize an input line of program code.
		The line must contain a complete program.
		"""
		def convert(token):
			if token in self.BOOLEANS:
				return bool(token)
			try:
				number = float(token)
				return number
			except ValueError:
				pass
			if len(token) > 1:
				quotes = token[0], token[-1]
				if quotes[0] == quotes[1] and quotes[0] in self.QUOTES:
					# must be a string
					return token[1:-1]
			# must be a reference
			return Reference(token)
		items = shlex.split(line, posix=False)
		tokens = []
		for item in items:
			# split the item on "(" and ")"
			tokens.extend([i for i in re.split(r"([\(\)])", item) if len(i) > 0])
		tokens = [convert(item) for item in tokens]
		#pdb.set_trace()
		return tokens

	def eval(self, line, count = 1, lookup = True):
		"""This method evaluates a complete program.
		It returns the count number of items from the bottom level stack, and looks
		up their values in the environment if requested.
		"""
		# each evaluation starts off with a new stack
		self.stacks = [[]]
		# parse the line into tokens
		tokens = self.tokenize(line)
		tokens.reverse()
		# evaluate one token at a time.
		while len(tokens) > 0:
			token = tokens.pop()
			if isinstance(token, Reference):
				if token.name == self.PUSHTOKEN:
					# push a new input stack on top of the old stack
					log("pre  pushing stacks:", self.stacks)
					self.pushstack()
					log("post pushing stacks:", self.stacks)
					continue
				elif token.name == self.POPTOKEN:
					# pop the current stack, add its value to the next stack
					log("pre  popping stacks:", self.stacks)
					self.popstack()
					log("post popping stacks:", self.stacks)
					continue
				elif self.makeoperator(token):
					# if it is a reference to an operator, feed the stack to the operator (and grab the result)
					continue
			# otherwise push it onto the stack
			self.push(token)
		# we need to make sure our stackdepth is 1
		if len(self.stacks) != 1:
			# probably a syntax error: no matching closing bracket.
			raise NestingException
		return self.pop(count, lookup)


#######################################################################
# Some unit test code follows:


def test():

	env = {
		'name': 'Jack',
	}

	p = Pretzyl(env)

	d = p.eval("(2 2 2 +*) 4 *")
	assert(d == 24)

	d = p.eval("   'hello [' name  ']!' +*2")
	assert(d == "hello [Jack]!")

	d = p.eval("True")
	assert(d == True)

	d = p.eval("5 4 <")
	assert(d == False)

	d = p.eval("4 5 <")
	assert(d == True)

	d = p.eval("5 4 < !")
	assert(d == True)

	d = p.eval("5 4 >=")
	assert(d == True)

	d = p.eval("'name' ~")
	assert(d == "Jack")

	d = p.eval("2 2 2 2 **")
	assert(d == 16)

	def testException(Exc, op):
		try:
			p.eval(op)
			assert(False)
		except Exc as e:
			pass

	testException(InvalidReference, "sammy")

	# these all look like operators, but they should
	# be rejected since each one has a syntax error.
	# This results in a lookup failure (ie. KeyError in the environment)
	testException(InvalidReference, "2 2 *%")
	testException(InvalidReference, "2 2 **x")
	testException(InvalidReference, "2 2 ***")
	testException(InvalidReference, "2 2 +#")
	testException(InvalidReference, "2 2 ^")

	# syntax errors - mismatched brackets
	testException(NestingException, "( ( )")
	testException(NestingException, "( ( ) ) )")

	# the operator expects two arguments, but there is only one
	testException(StackUnderflow, "highlander +")
	p.STACKLIMIT = 10
	testException(StackOverflow, "0 1 2 3 4 5 6 7 8 9 10")
	p.STACKDEPTH = 5
	testException(RecursionOverflow, "( ( ( ( ( ( ) ) ) ) ) )")
	p.INFLIMIT = 5
	testException(IterationOverflow, "0 1 2 3 4 5 6 **")

	return 0

if __name__ == "__main__":
	import traceback
	import pdb
	try:
		result = test()
	except:
		traceback.print_exc()
		pdb.post_mortem()
	sys.exit(result)
